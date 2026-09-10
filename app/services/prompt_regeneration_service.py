from __future__ import annotations

import logging
import time
from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt
from app.repositories.prompt import PromptRepository
from app.repositories.template import TemplateRepository
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.exceptions import (
    PromptNotFoundError,
    PromptVersionException,
    DatabaseTransactionException,
)

logger = logging.getLogger("promptiq.prompt_regeneration")

class PromptRegenerationService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        template_repository: TemplateRepository,
        prompt_version_service: PromptVersionService,
        prompt_embedding_service: PromptEmbeddingService,
        analysis_service: PromptAnalysisService,
        llm_provider: BaseLLMProvider,
        enhancement_service: Any,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.template_repository = template_repository
        self.prompt_version_service = prompt_version_service
        self.prompt_embedding_service = prompt_embedding_service
        self.analysis_service = analysis_service
        self.llm_provider = llm_provider
        self.enhancement_service = enhancement_service

    async def regenerate_prompt(
        self,
        session: AsyncSession,
        prompt_id: str,
        feedback: Optional[str] = None,
    ) -> dict[str, Any]:
        total_start = time.perf_counter()
        logger.info("Starting prompt regeneration with feedback for prompt_id=%s", prompt_id)

        # 1. Load prompt
        prompt = await self.prompt_repository.get_by_id(session, prompt_id, include_template=True)
        
        # 2. Validate Prompt Exists
        if not prompt or getattr(prompt, "deleted_at", None) is not None:
            raise PromptNotFoundError(f"Prompt with ID {prompt_id} not found or deleted.")

        # Validate Prompt has active version
        if not prompt.current_version_id:
            raise PromptVersionException("Prompt has no active version.")

        # Load Template Used (if any)
        template = None
        if prompt.template_id:
            template = prompt.template
            if not template:
                template = await self.template_repository.get_by_id(session, str(prompt.template_id))
            if not template:
                raise PromptVersionException("Prompt template not found.")

        # 3. Apply User Feedback
        merged_prompt = prompt.original_prompt
        if feedback and feedback.strip():
            logger.info("Applying user feedback: '%s'", feedback)
            llm_prompt = (
                "You are an assistant that modifies user prompts based on their natural language feedback.\n"
                "Given the original prompt and the user's feedback, produce a single merged prompt that incorporates the feedback.\n"
                "Do NOT enhance or optimize the prompt yet, just apply the feedback to the original prompt text.\n\n"
                f"Original Prompt: {prompt.original_prompt}\n"
                f"Feedback: {feedback}\n\n"
                "Output ONLY the merged prompt text. Do not include any introductory text, explanation, or formatting."
            )
            try:
                res = await self.llm_provider.generate(llm_prompt, temperature=0.1)
                merged_prompt = res.text.strip()
            except Exception as exc:
                logger.exception("LLM feedback merge failed, falling back to original prompt")
                merged_prompt = prompt.original_prompt

        # 4. Call PromptEnhancementService
        llm_start = time.perf_counter()
        try:
            enhance_res = await self.enhancement_service.enhance_prompt(
                session=session,
                role=template.role if template else None,
                mode=template.mode if template else None,
                prompt=merged_prompt,
                template_override=template,
            )
        except Exception as exc:
            logger.exception("Prompt enhancement failed during regeneration")
            raise PromptVersionException("Prompt enhancement failed.") from exc
        llm_time = time.perf_counter() - llm_start
        enhanced_prompt = enhance_res["enhanced_prompt"]

        # 5. Analyze Prompt Quality
        try:
            analysis = await self.analysis_service.analyze(enhanced_prompt)
        except Exception as exc:
            logger.exception("Prompt analysis failed during regeneration")
            raise PromptVersionException("Prompt analysis failed.") from exc

        # 6. Database transactional persistence
        emb_start = time.perf_counter()
        try:
            # Create new sequential version (type = REGENERATION)
            new_version = await self.prompt_version_service.create_version(
                session=session,
                prompt=prompt,
                content=enhanced_prompt,
                version_type="REGENERATION",
                change_summary=f"Prompt regenerated using feedback: {feedback}" if feedback else "Prompt regenerated using the same template.",
                template_id=prompt.template_id,
            )
            await session.flush()

            # Generate new embedding
            await self.prompt_embedding_service.update_prompt_embedding(session, str(prompt.id))
            
            # Update prompt overall score & grade
            grade_after = analysis["grade"]
            overall_score_scaled = analysis["overall_score"]
            
            prompt.new_analysis = analysis
            prompt.grade = grade_after
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()
            
            # Commit transaction
            await session.commit()
            transaction_status = "COMMITTED"
        except Exception as exc:
            logger.exception("Regeneration transaction failed. Rolling back.")
            transaction_status = "ROLLED_BACK"
            await session.rollback()
            raise DatabaseTransactionException("Failed to persist regenerated prompt.") from exc
        
        emb_time = time.perf_counter() - emb_start
        total_time = time.perf_counter() - total_start

        # Log according to specification
        logger.info(
            "Regeneration completed. Prompt ID: %s | Current Version: %d | New Version: %d | "
            "Template Used: %s | LLM Response Time: %.4fs | Embedding Generation Time: %.4fs | "
            "Transaction Status: %s | Total Execution Time: %.4fs",
            str(prompt.id),
            new_version.version_number - 1,
            new_version.version_number,
            template.title,
            llm_time,
            emb_time,
            transaction_status,
            total_time,
        )

        return {
            "success": True,
            "message": "Prompt regenerated successfully.",
            "data": {
                "prompt_id": str(prompt.id),
                "version_number": new_version.version_number,
                "enhanced_prompt": enhanced_prompt,
                "analysis": {
                    "overall_score": overall_score_scaled,
                    "grade": grade_after,
                },
            },
        }
