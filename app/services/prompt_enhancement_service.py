from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.exceptions import (
    PromptValidationException,
    PromptEnhancementException,
    TemplateRenderException,
    LLMTimeoutException,
    LLMResponseException,
)
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import LLMTimeoutError, LLMRequestError
from app.services.template_retrieval_service import TemplateRetrievalService
from app.services.template_renderer import TemplateRenderer
from app.services.prompt_builder import PromptBuilder
from app.services.prompt_sanitizer import neutralize_delimiters, sanitize_variables
from app.services.template_variable_extractor import TemplateVariableExtractor

logger = logging.getLogger("promptiq.prompt_enhancement")


class PromptEnhancementService:
    """
    PromptEnhancementService orchestrates the full prompt enhancement flow:
    retrieving templates, rendering variables, building prompts, communicating
    with LLM (with retries), and validating the output prompt.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        retrieval_service: TemplateRetrievalService,
        template_renderer: Optional[TemplateRenderer] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        variable_extractor: Optional[TemplateVariableExtractor] = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.retrieval_service = retrieval_service
        self.template_renderer = template_renderer or TemplateRenderer()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.variable_extractor = variable_extractor or TemplateVariableExtractor(llm_provider=self.llm_provider)

    async def enhance_prompt(
        self,
        session: AsyncSession,
        role: Optional[str] = None,
        mode: Optional[str] = None,
        prompt: str = "",
        variables: Optional[dict[str, str]] = None,
        style_attributes: Optional[dict[str, Any]] = None,
        template_override: Optional[Any] = None,
        enhancement_level: str = "standard",
    ) -> dict:
        logger.info("Starting prompt enhancement request")
        
        # STEP 1: Validate request parameters
        if not prompt or not prompt.strip():
            raise PromptValidationException("Prompt content cannot be empty.")
        if len(prompt) > 12000:
            raise PromptValidationException(f"Prompt content is too long ({len(prompt)} chars). Max 12000 chars.")

        # Sanitize all user-controlled inputs before any LLM interpolation.
        # This collapses structural delimiter runs (===, <<<, >>>, ```) that
        # could otherwise forge trusted section boundaries inside the prompt.
        prompt = neutralize_delimiters(prompt)
        variables = sanitize_variables(variables)

        # STEP 2: Retrieve a template for a new enhancement, or use the
        # persisted template for re-enhancement. The latter must not trigger
        # semantic retrieval/embedding generation again.
        if template_override is not None:
            selected_temp = {
                "id": str(template_override.id),
                "title": template_override.title,
                "body": template_override.body,
            }
            similarity_score = 1.0
        else:
            retrieval_res = await self.retrieval_service.retrieve_best_template(
                session=session,
                role=role,
                mode=mode,
                prompt=prompt,
                variables=variables,
            )
            selected_temp = retrieval_res["selected_template"]
            similarity_score = retrieval_res["similarity_score"]
        template_id = selected_temp["id"]
        template_body = selected_temp["body"]

        # STEP 2.5: Dynamically infer / extract template variables from the user prompt
        extracted_vars = await self.variable_extractor.extract_variables(
            prompt=prompt,
            template_body=template_body,
            user_variables=variables,
        )
        effective_vars = {**extracted_vars, **(variables or {})}
        effective_vars.setdefault("REQUEST", prompt)

        # STEP 3: Render placeholders inside the template body
        try:
            rendered_template = self.template_renderer.render(
                template_body=template_body,
                user_prompt=prompt,
                variables=effective_vars,
            )
        except TemplateRenderException as exc:
            logger.exception("Template rendering failed")
            raise exc
        except Exception as exc:
            logger.exception("Unexpected rendering error")
            raise TemplateRenderException("Unexpected error during template variable rendering.") from exc

        # STEP 4 & 5: Build final prompt and call LLM with retry strategy
        max_retries = settings.max_retries
        current_try = 0
        strong_sys_instructions: Optional[str] = None

        while current_try <= max_retries:
            try:
                # Use build_messages() so system guardrails are sent as a
                # real system-role message and all user-derived content
                # (role, mode, template, raw prompt) stays in the user message.
                # This system/user separation is the primary injection defense.
                messages = self.prompt_builder.build_messages(
                    role=role,
                    mode=mode,
                    rendered_template=rendered_template,
                    system_instructions=strong_sys_instructions,
                    style_attributes=style_attributes,
                    enhancement_level=enhancement_level,
                )

                logger.info(
                    "Calling LLM provider. System size: %d chars, user size: %d chars",
                    len(messages["system"]),
                    len(messages["user"]),
                )

                # Profile LLM Latency
                start_time = time.perf_counter()
                result = await self.llm_provider.optimize_prompt(
                    prompt=messages["user"],
                    system=messages["system"],
                    template_id=template_id,
                    max_tokens=settings.llm_optimization_max_tokens,
                )
                latency = time.perf_counter() - start_time

                enhanced_prompt = self._clean_enhanced_output(result.optimized_prompt)

                # Validate Response content
                if not enhanced_prompt or not isinstance(enhanced_prompt, str):
                    raise LLMResponseException("LLM provider returned an empty or invalid content response.")

                # Check if LLM solved the task instead of optimizing the prompt
                if self.is_task_execution(enhanced_prompt, prompt):
                    logger.warning("LLM output looks like direct task execution. Retrying with stronger guidelines...")
                    # Prepare stronger instructions warning for next attempt
                    strong_sys_instructions = (
                        f"{PromptBuilder.DEFAULT_SYSTEM_INSTRUCTIONS}\n\n"
                        f"CRITICAL WARNING: Your previous response resolved the user's prompt (executed the task) instead of enhancing the prompt. "
                        f"You must NEVER answer the request. For example, if the user request is 'Find my ideal customer', you must output "
                        f"a prompt template like 'Act as a marketer, define target demographics...', NOT a list of customers. "
                        f"Generate ONLY the enhanced prompt. DO NOT solve the task!"
                    )
                    raise LLMResponseException("LLM provider returned task execution instead of prompt enhancement.")

                logger.info("Prompt enhanced successfully. Latency: %.4fs, attempts: %d", latency, current_try + 1)
                return {
                    "enhanced_prompt": enhanced_prompt,
                    "template_id": template_id,
                    "template_title": selected_temp["title"],
                    "similarity_score": similarity_score,
                    "variables": effective_vars,
                }

            except LLMTimeoutError as exc:
                current_try += 1
                if current_try > max_retries:
                    raise LLMTimeoutException("LLM API request timed out after maximum retries.") from exc
                await self._backoff_sleep(current_try)

            except (LLMRequestError, LLMResponseException) as exc:
                current_try += 1
                if current_try > max_retries:
                    raise PromptEnhancementException("Failed to enhance prompt after maximum retries due to LLM errors.") from exc
                await self._backoff_sleep(current_try)

        raise PromptEnhancementException("Max retries exceeded during prompt optimization.")

    async def enhance_prompt_stream(
        self,
        session: AsyncSession,
        role: Optional[str] = None,
        mode: Optional[str] = None,
        prompt: str = "",
        variables: Optional[dict[str, str]] = None,
        style_attributes: Optional[dict[str, Any]] = None,
        template_override: Optional[Any] = None,
        enhancement_level: str = "standard",
    ) -> AsyncIterator[dict]:
        """Streaming counterpart of :meth:`enhance_prompt`.

        Runs the same template retrieval / rendering / prompt-building steps,
        then streams the LLM output as it is generated. Yields event dicts::

            {"type": "meta",  "template_id", "template_title", "similarity_score"}
            {"type": "delta", "text": "<raw fragment>"}          (repeated)
            {"type": "final", "enhanced_prompt", "template_id", ...}

        Unlike the blocking path there is no multi-attempt retry loop: tokens
        are emitted as soon as they arrive, so a mid-stream failure cannot be
        retried transparently. Callers should surface an error event and may
        fall back to :meth:`enhance_prompt`.
        """
        logger.info("Starting streaming prompt enhancement request")

        # STEP 1: Validate request parameters (mirrors enhance_prompt)
        if not prompt or not prompt.strip():
            raise PromptValidationException("Prompt content cannot be empty.")
        if len(prompt) > 12000:
            raise PromptValidationException(f"Prompt content is too long ({len(prompt)} chars). Max 12000 chars.")

        # Sanitize user-controlled inputs before LLM interpolation.
        prompt = neutralize_delimiters(prompt)
        variables = sanitize_variables(variables)

        # STEP 2: Template selection (explicit override or semantic retrieval)
        if template_override is not None:
            selected_temp = {
                "id": str(template_override.id),
                "title": template_override.title,
                "body": template_override.body,
            }
            similarity_score = 1.0
        else:
            retrieval_res = await self.retrieval_service.retrieve_best_template(
                session=session,
                role=role,
                mode=mode,
                prompt=prompt,
                variables=variables,
            )
            selected_temp = retrieval_res["selected_template"]
            similarity_score = retrieval_res["similarity_score"]
        template_id = selected_temp["id"]
        template_body = selected_temp["body"]

        # STEP 2.5: Dynamically infer / extract template variables from the user prompt
        extracted_vars = await self.variable_extractor.extract_variables(
            prompt=prompt,
            template_body=template_body,
            user_variables=variables,
        )
        effective_vars = {**extracted_vars, **(variables or {})}
        effective_vars.setdefault("REQUEST", prompt)

        # STEP 3: Render placeholders inside the template body
        try:
            rendered_template = self.template_renderer.render(
                template_body=template_body,
                user_prompt=prompt,
                variables=effective_vars,
            )
        except TemplateRenderException as exc:
            logger.exception("Template rendering failed")
            raise exc
        except Exception as exc:
            logger.exception("Unexpected rendering error")
            raise TemplateRenderException("Unexpected error during template variable rendering.") from exc

        # STEP 4: Build system/user messages. Single attempt — streaming cannot
        # transparently retry once bytes have been sent to the client.
        messages = self.prompt_builder.build_messages(
            role=role,
            mode=mode,
            rendered_template=rendered_template,
            system_instructions=None,
            style_attributes=style_attributes,
            enhancement_level=enhancement_level,
        )

        # Emit template metadata up front so the client can render context
        # (template name, similarity) before the first token arrives.
        yield {
            "type": "meta",
            "template_id": template_id,
            "template_title": selected_temp["title"],
            "similarity_score": similarity_score,
            "variables": effective_vars,
        }

        # STEP 5: Stream tokens, accumulating raw text for post-processing.
        logger.info(
            "Streaming LLM provider. System size: %d chars, user size: %d chars",
            len(messages["system"]),
            len(messages["user"]),
        )
        start_time = time.perf_counter()
        buffer: list[str] = []
        async for delta in self.llm_provider.optimize_prompt_stream(
            prompt=messages["user"],
            system=messages["system"],
            max_tokens=settings.llm_optimization_max_tokens,
        ):
            buffer.append(delta)
            yield {"type": "delta", "text": delta}
        latency = time.perf_counter() - start_time

        raw_output = "".join(buffer)
        enhanced_prompt = self._clean_enhanced_output(raw_output)

        if not enhanced_prompt or not isinstance(enhanced_prompt, str):
            raise LLMResponseException("LLM provider returned an empty or invalid content response.")

        # Best-effort guard: the blocking path retries on task-execution slips,
        # but a stream has already emitted its bytes, so we only log here.
        if self.is_task_execution(enhanced_prompt, prompt):
            logger.warning("Streamed LLM output looks like direct task execution (not retried in stream mode).")

        logger.info("Streaming prompt enhanced successfully. Latency: %.4fs", latency)
        yield {
            "type": "final",
            "enhanced_prompt": enhanced_prompt,
            "template_id": template_id,
            "template_title": selected_temp["title"],
            "similarity_score": similarity_score,
            "variables": effective_vars,
        }

    async def _backoff_sleep(self, attempt: int) -> None:
        sleep_time = 2 ** attempt
        logger.warning("Transient error or validation failure. Retrying in %ds...", sleep_time)
        await asyncio.sleep(sleep_time)

    def is_task_execution(self, text: str, original_prompt: str) -> bool:
        text_lower = text.strip().lower()
        # Heuristics:
        # 1. Check direct conversational answer prefixes
        conversational_headers = [
            "here is", "sure, here", "the ideal customer", "i can help you",
            "i will write", "i will do", "the answer is", "here are"
        ]
        for header in conversational_headers:
            if text_lower.startswith(header):
                return True

        # 2. Lack of directive keywords (meaning it directly answered without structure)
        directives = ["act as", "you are", "your task", "your role", "system prompt", "instructions:", "context:", "objective:"]
        has_directives = any(d in text_lower for d in directives)
        if not has_directives:
            return True

        return False

    def _clean_enhanced_output(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""

        cleaned = text.strip()

        # If "ENHANCED PROMPT:" exists, extract everything after it
        markers = ["ENHANCED PROMPT:", "ENHANCED PROMPT", "Enhanced Prompt:"]
        for m in markers:
            idx = cleaned.find(m)
            if idx != -1:
                cleaned = cleaned[idx + len(m):].strip()
                break
        else:
            # Case insensitive search fallback
            lower_text = cleaned.lower()
            idx_lower = lower_text.find("enhanced prompt:")
            if idx_lower != -1:
                cleaned = cleaned[idx_lower + len("enhanced prompt:"):].strip()

        # Strip lingering markdown code fence wrapper if entire response was wrapped
        if cleaned.startswith("```"):
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()
