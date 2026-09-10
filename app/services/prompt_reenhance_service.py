from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Optional, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt
from app.repositories.prompt import PromptRepository
from app.repositories.template import TemplateRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.tool_recommendation_service import ToolRecommendationService
from app.services.exceptions import (
    PromptNotFoundError,
    PromptVersionException,
    DatabaseTransactionException,
)

logger = logging.getLogger("promptiq.prompt_reenhance")


class PromptReenhanceService:
    """
    Re-enhance a prompt by taking the latest version's content and running it
    through the same template that was originally selected — no template search
    needed since the template_id is already stored on the prompt record.

    Creates a new PromptVersion (type='reenhancement') with per-version
    old_analysis and new_analysis so the chat history UI can show independent
    scores per version. Never creates a new Prompt row.
    """

    def __init__(
        self,
        prompt_repository: PromptRepository,
        template_repository: TemplateRepository,
        prompt_version_repository: PromptVersionRepository,
        prompt_version_service: PromptVersionService,
        prompt_embedding_service: PromptEmbeddingService,
        analysis_service: PromptAnalysisService,
        tool_recommendation_service: ToolRecommendationService,
        enhancement_service: Any,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.template_repository = template_repository
        self.prompt_version_repository = prompt_version_repository
        self.prompt_version_service = prompt_version_service
        self.prompt_embedding_service = prompt_embedding_service
        self.analysis_service = analysis_service
        self.tool_recommendation_service = tool_recommendation_service
        self.enhancement_service = enhancement_service

    async def reenhance_prompt(
        self,
        session: AsyncSession,
        prompt_id: str,
    ) -> dict[str, Any]:
        total_start = time.perf_counter()
        logger.info("Starting re-enhancement for prompt_id=%s", prompt_id)

        # ── 1. Load and validate prompt ───────────────────────────────────────
        prompt = await self.prompt_repository.get_by_id(session, prompt_id, include_template=True)

        if not prompt or getattr(prompt, "deleted_at", None) is not None:
            raise PromptNotFoundError(f"Prompt {prompt_id} not found or deleted.")

        if not prompt.current_version_id:
            raise PromptVersionException("Prompt has no active version to re-enhance.")

        # ── 2. Load template (if linked) ──────────────────────────────────────
        template = None
        if prompt.template_id:
            template = prompt.template
            if not template:
                template = await self.template_repository.get_by_id(session, str(prompt.template_id))
            if not template:
                raise PromptVersionException(
                    f"Template {prompt.template_id} not found. Cannot re-enhance."
                )

        # ── 3. Get the latest version's content as the INPUT to re-enhance ───
        latest_version = await self.prompt_version_repository.get_latest_version(
            session, prompt_id
        )
        if not latest_version:
            raise PromptVersionException("No versions found for this prompt.")

        input_text = latest_version.content

        # ── 4. old_analysis for the new version ────────────────────────────────
        # For ANY version, the previous version's new_analysis IS the starting score.
        # Carry it forward; only compute fresh when it is absent.
        if latest_version.new_analysis:
            old_analysis = latest_version.new_analysis
            logger.info(
                "Re-using new_analysis from v%d as old_analysis for re-enhancement.",
                latest_version.version_number,
            )
        elif prompt.new_analysis:
            old_analysis = prompt.new_analysis
            logger.info(
                "Re-using new_analysis from prompt table as old_analysis for re-enhancement."
            )
        else:
            logger.info(
                "No cached new_analysis available — computing old_analysis from input text."
            )
            try:
                old_analysis = await self.analysis_service.analyze(input_text)
            except Exception as exc:
                logger.exception("Analysis of input text failed during re-enhancement")
                raise PromptVersionException("Failed to analyse input prompt.") from exc

        # ── 5. Run enhancement using the pre-selected template ────────────────
        llm_start = time.perf_counter()
        try:
            enhance_res = await self.enhancement_service.enhance_prompt(
                session=session,
                role=template.role if template else None,
                mode=template.mode if template else None,
                prompt=input_text,
                template_override=template,
            )
        except Exception as exc:
            logger.exception("Prompt enhancement failed during re-enhancement")
            raise PromptVersionException("Prompt enhancement failed.") from exc
        llm_time = time.perf_counter() - llm_start
        enhanced_text = enhance_res["enhanced_prompt"]

        # ── 6. Analyze the OUTPUT (this becomes new_analysis for the new version)
        try:
            new_analysis = await self.analysis_service.analyze(enhanced_text)
        except Exception as exc:
            logger.exception("Analysis of enhanced text failed during re-enhancement")
            raise PromptVersionException("Failed to analyse enhanced prompt.") from exc

        # ── 7. Get tool recommendations ───────────────────────────────────────
        # • Version 1: the recommendations are stored on the version row (with fallback to prompts table)
        # • Version 2+: carry forward from the previous version when present.
        # In both cases fall back to a fresh recommendation call only when absent.
        if latest_version.version_number == 1 and (latest_version.tool_recommendations or prompt.tool_recommendations):
            tool_rec_dict = latest_version.tool_recommendations or prompt.tool_recommendations
            logger.info(
                "v1 re-enhancement: using tool_recommendations for prompt_id=%s.",
                prompt_id,
            )
        elif latest_version.version_number != 1 and latest_version.tool_recommendations:
            tool_rec_dict = latest_version.tool_recommendations
            logger.info(
                "Carrying forward tool_recommendations from v%d.",
                latest_version.version_number,
            )
        else:
            logger.info(
                "No cached tool_recommendations available — computing fresh recommendations."
            )
            try:
                tool_rec = await self.tool_recommendation_service.recommend(
                    prompt=input_text,
                    mode=template.mode if template else None,
                    role=template.role if template else None,
                )
            except Exception:
                logger.warning("Tool recommendation failed during re-enhancement — using fallback")
                tool_rec = self.tool_recommendation_service.get_fallback()

            tool_rec_dict = {
                "matched_task": tool_rec["matched_task"],
                "match_type": tool_rec.get("match_type", "fallback"),
                "match_confidence": tool_rec.get("match_confidence", 0.5),
                "tools": tool_rec["tools"],
            }

        # ── 8. Persist new version ────────────────────────────────────────────
        emb_start = time.perf_counter()
        try:
            grade_after = new_analysis.get("grade", "B")

            new_version = await self.prompt_version_service.create_version(
                session=session,
                prompt=prompt,
                content=enhanced_text,
                version_type="REENHANCEMENT",
                change_summary=(
                    f"Re-enhanced from v{latest_version.version_number}."
                ),
                old_analysis=old_analysis,
                new_analysis=new_analysis,
                tool_recommendations=tool_rec_dict,
                template_id=prompt.template_id,
            )
            await session.flush()

            # Update prompt latest scores
            prompt.new_analysis = new_analysis
            prompt.grade = grade_after
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()

            # The version itself is the user-facing result. Embeddings support
            # search and must not make re-enhancement fail when the embedding
            # model is temporarily unavailable.
            try:
                await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
                await session.flush()
            except Exception:
                logger.warning(
                    "Could not refresh embedding after re-enhancement for prompt_id=%s; "
                    "the version was still saved.",
                    prompt_id,
                    exc_info=True,
                )

            await session.commit()
            transaction_status = "COMMITTED"
        except Exception as exc:
            logger.exception("Re-enhancement transaction failed. Rolling back.")
            transaction_status = "ROLLED_BACK"
            await session.rollback()
            raise DatabaseTransactionException("Failed to persist re-enhanced version.") from exc


        emb_time = time.perf_counter() - emb_start
        total_time = time.perf_counter() - total_start

        logger.info(
            "Re-enhancement completed. prompt_id=%s | v%d -> v%d | template=%s | "
            "LLM=%.3fs | embed=%.3fs | total=%.3fs | status=%s",
            prompt_id,
            latest_version.version_number,
            new_version.version_number,
            template.title if template else "Adaptive",
            llm_time,
            emb_time,
            total_time,
            transaction_status,
        )

        return {
            "success": True,
            "message": "Prompt re-enhanced successfully.",
            "data": {
                "prompt_id": str(prompt.id),
                "version_id": str(new_version.id),
                "version_number": new_version.version_number,
                "enhanced_prompt": enhanced_text,
                "template_id": str(prompt.template_id) if prompt.template_id else "adaptive",
                "old_analysis": old_analysis,
                "new_analysis": new_analysis,
                "tool_recommendations": tool_rec_dict,
            },
        }

    async def reenhance_prompt_stream(
        self,
        session: AsyncSession,
        prompt_id: str,
    ) -> AsyncIterator[dict]:
        """Streaming counterpart of :meth:`reenhance_prompt`.

        Runs the identical load / validate / template / score-carry-forward /
        persist logic, but streams the LLM enhancement token-by-token instead of
        blocking on the full response. Yields event dicts::

            {"type": "meta",  "template_id", "template_title", "similarity_score"}
            {"type": "delta", "text": "<raw fragment>"}          (repeated)
            {"type": "final", "data": {... same shape as reenhance_prompt()['data'] ...}}

        The quality scores (old_analysis / new_analysis) and tool recommendations
        are still computed synchronously here — right after the token stream ends
        — and travel in the ``final`` event, so the client receives everything in
        one stream, exactly as the blocking endpoint returns it in one response
        (no follow-up polling needed). This method deliberately mirrors the
        blocking path step-for-step rather than sharing helpers, so the blocking
        fallback stays byte-for-byte unchanged.
        """
        total_start = time.perf_counter()
        logger.info("Starting streaming re-enhancement for prompt_id=%s", prompt_id)

        # ── 1. Load and validate prompt ───────────────────────────────────────
        prompt = await self.prompt_repository.get_by_id(session, prompt_id, include_template=True)
        if not prompt or getattr(prompt, "deleted_at", None) is not None:
            raise PromptNotFoundError(f"Prompt {prompt_id} not found or deleted.")
        if not prompt.current_version_id:
            raise PromptVersionException("Prompt has no active version to re-enhance.")

        # ── 2. Load template (if linked) ──────────────────────────────────────
        template = None
        if prompt.template_id:
            template = prompt.template
            if not template:
                template = await self.template_repository.get_by_id(session, str(prompt.template_id))
            if not template:
                raise PromptVersionException(
                    f"Template {prompt.template_id} not found. Cannot re-enhance."
                )

        # ── 3. Latest version's content is the INPUT to re-enhance ────────────
        latest_version = await self.prompt_version_repository.get_latest_version(
            session, prompt_id
        )
        if not latest_version:
            raise PromptVersionException("No versions found for this prompt.")
        input_text = latest_version.content

        # ── 4. old_analysis for the new version (carry forward, else compute) ──
        if latest_version.new_analysis:
            old_analysis = latest_version.new_analysis
        elif prompt.new_analysis:
            old_analysis = prompt.new_analysis
        else:
            try:
                old_analysis = await self.analysis_service.analyze(input_text)
            except Exception as exc:
                logger.exception("Analysis of input text failed during streaming re-enhancement")
                raise PromptVersionException("Failed to analyse input prompt.") from exc

        # ── 5. Stream enhancement using the pre-selected template ─────────────
        # Single attempt (no retry): once tokens have been emitted the stream
        # can't be transparently retried, so any failure here is surfaced as an
        # error to the caller, which may fall back to the blocking endpoint.
        llm_start = time.perf_counter()
        enhanced_text: Optional[str] = None
        try:
            async for ev in self.enhancement_service.enhance_prompt_stream(
                session=session,
                role=template.role if template else None,
                mode=template.mode if template else None,
                prompt=input_text,
                template_override=template,
            ):
                etype = ev.get("type")
                if etype == "meta":
                    yield {
                        "type": "meta",
                        "template_id": ev["template_id"],
                        "template_title": ev["template_title"],
                        "similarity_score": ev["similarity_score"],
                    }
                elif etype == "delta":
                    yield {"type": "delta", "text": ev["text"]}
                elif etype == "final":
                    enhanced_text = ev["enhanced_prompt"]
        except Exception as exc:
            logger.exception("Prompt enhancement failed during streaming re-enhancement")
            raise PromptVersionException("Prompt enhancement failed.") from exc
        llm_time = time.perf_counter() - llm_start

        if not enhanced_text:
            raise PromptVersionException("Streaming ended before producing a re-enhanced result.")

        # ── 6. Analyze the OUTPUT (new_analysis for the new version) ──────────
        try:
            new_analysis = await self.analysis_service.analyze(enhanced_text)
        except Exception as exc:
            logger.exception("Analysis of enhanced text failed during streaming re-enhancement")
            raise PromptVersionException("Failed to analyse enhanced prompt.") from exc

        # ── 7. Tool recommendations (carry forward, else compute) ─────────────
        if latest_version.version_number == 1 and (latest_version.tool_recommendations or prompt.tool_recommendations):
            tool_rec_dict = latest_version.tool_recommendations or prompt.tool_recommendations
        elif latest_version.version_number != 1 and latest_version.tool_recommendations:
            tool_rec_dict = latest_version.tool_recommendations
        else:
            try:
                tool_rec = await self.tool_recommendation_service.recommend(
                    prompt=input_text,
                    mode=template.mode,
                    role=template.role,
                )
            except Exception:
                logger.warning("Tool recommendation failed during streaming re-enhancement — using fallback")
                tool_rec = self.tool_recommendation_service.get_fallback()
            tool_rec_dict = {
                "matched_task": tool_rec["matched_task"],
                "match_type": tool_rec.get("match_type", "fallback"),
                "match_confidence": tool_rec.get("match_confidence", 0.5),
                "tools": tool_rec["tools"],
            }

        # ── 8. Persist new version ────────────────────────────────────────────
        emb_start = time.perf_counter()
        try:
            grade_after = new_analysis.get("grade", "B")

            new_version = await self.prompt_version_service.create_version(
                session=session,
                prompt=prompt,
                content=enhanced_text,
                version_type="REENHANCEMENT",
                change_summary=(
                    f"Re-enhanced from v{latest_version.version_number}."
                ),
                old_analysis=old_analysis,
                new_analysis=new_analysis,
                tool_recommendations=tool_rec_dict,
                template_id=prompt.template_id,
            )
            await session.flush()

            prompt.new_analysis = new_analysis
            prompt.grade = grade_after
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()

            # Embeddings support search and must not make re-enhancement fail
            # when the embedding model is temporarily unavailable.
            try:
                await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
                await session.flush()
            except Exception:
                logger.warning(
                    "Could not refresh embedding after streaming re-enhancement for prompt_id=%s; "
                    "the version was still saved.",
                    prompt_id,
                    exc_info=True,
                )

            await session.commit()
            transaction_status = "COMMITTED"
        except Exception as exc:
            logger.exception("Streaming re-enhancement transaction failed. Rolling back.")
            transaction_status = "ROLLED_BACK"
            await session.rollback()
            raise DatabaseTransactionException("Failed to persist re-enhanced version.") from exc

        emb_time = time.perf_counter() - emb_start
        total_time = time.perf_counter() - total_start
        logger.info(
            "Streaming re-enhancement completed. prompt_id=%s | v%d -> v%d | template=%s | "
            "LLM=%.3fs | embed=%.3fs | total=%.3fs | status=%s",
            prompt_id,
            latest_version.version_number,
            new_version.version_number,
            template.title if template else "Adaptive",
            llm_time,
            emb_time,
            total_time,
            transaction_status,
        )

        yield {
            "type": "final",
            "data": {
                "prompt_id": str(prompt.id),
                "version_id": str(new_version.id),
                "version_number": new_version.version_number,
                "enhanced_prompt": enhanced_text,
                "template_id": str(prompt.template_id) if prompt.template_id else "adaptive",
                "old_analysis": old_analysis,
                "new_analysis": new_analysis,
                "tool_recommendations": tool_rec_dict,
            },
        }

