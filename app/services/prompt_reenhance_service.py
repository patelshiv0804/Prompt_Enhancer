from __future__ import annotations

import logging
import time
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

        if not prompt.template_id:
            raise PromptVersionException(
                "Prompt has no linked template. Re-enhance requires the original template."
            )

        # ── 2. Load template ──────────────────────────────────────────────────
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

        # ── 4. Analyze the INPUT (this becomes old_analysis for the new version)
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
                role=template.role,
                mode=template.mode,
                prompt=input_text,
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
        try:
            tool_rec = await self.tool_recommendation_service.recommend(
                prompt=input_text,
                mode=template.mode,
                role=template.role,
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
                    f"Re-enhanced from v{latest_version.version_number} using template '{template.title}'."
                ),
                old_analysis=old_analysis,
                new_analysis=new_analysis,
                tool_recommendations=tool_rec_dict,
                template_id=str(prompt.template_id),
            )
            await session.flush()

            # Update prompt latest scores
            prompt.new_analysis = new_analysis
            prompt.grade = grade_after
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()

            # Regenerate embedding from latest version content
            await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
            await session.flush()

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
            template.title,
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
                "template_id": str(prompt.template_id),
                "old_analysis": old_analysis,
                "new_analysis": new_analysis,
                "tool_recommendations": tool_rec_dict,
            },
        }

