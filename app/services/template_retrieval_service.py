from __future__ import annotations

import logging
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.template import TemplateRepository
from app.services.embedding_service import EmbeddingService
from app.services.ranking_service import RankingService
from app.services.exceptions import (
    InvalidRoleError,
    InvalidModeError,
    EmbeddingGenerationError,
    NoTemplatesFoundError,
    SimilarityBelowThresholdError,
    DatabaseFailureError,
)

logger = logging.getLogger("promptiq.template_retrieval")


class TemplateRetrievalService:
    """
    TemplateRetrievalService coordinates validation, prompt embedding generation,
    candidate filtering, similarity search, and template ranking.
    """

    def __init__(
        self,
        repository: TemplateRepository,
        ranking_service: RankingService,
        embedding_service: Optional[EmbeddingService] = None,
        intent_service: Optional[Any] = None,
        role_resolver: Optional[Any] = None,
        mode_resolver: Optional[Any] = None,
        candidate_service: Optional[Any] = None,
    ) -> None:
        self.repository = repository
        self.ranking_service = ranking_service
        self.embedding_service = embedding_service or EmbeddingService()
        self.intent_service = intent_service
        self.role_resolver = role_resolver
        self.mode_resolver = mode_resolver
        self.candidate_service = candidate_service

    async def retrieve_best_template(
        self,
        session: AsyncSession,
        role: Optional[str],
        mode: Optional[str],
        prompt: str,
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
        variables: Optional[dict[str, str]] = None,
    ) -> dict:
        total_start = time.perf_counter()
        logger.info("Incoming template search request for role='%s' mode='%s'", role, mode)

        # STEP 1: Validate prompt
        if not prompt or not prompt.strip():
            raise EmbeddingGenerationError("Prompt parameter is required and cannot be empty for embedding generation.")

        # Query distinct roles and modes from db
        distinct_roles = await self.repository.get_distinct_roles(session)
        distinct_modes = await self.repository.get_distinct_modes(session)

        # Intent inference if role or mode is missing
        original_role = role
        original_mode = mode
        inferred_role = None
        inferred_mode = None

        if (not role or not role.strip()) or (not mode or not mode.strip()):
            if self.intent_service:
                inferred = await self.intent_service.analyze_intent(
                    prompt=prompt,
                    variables=variables,
                    provided_role=role,
                    provided_mode=mode,
                    distinct_roles=distinct_roles,
                    distinct_modes=distinct_modes,
                )
                inferred_role = inferred.get("inferred_role")
                inferred_mode = inferred.get("inferred_mode")
                
            role = role or inferred_role
            mode = mode or inferred_mode

        # If still missing after inference, fallback to first available
        if not role or not role.strip():
            role = distinct_roles[0] if distinct_roles else "Marketer"
        if not mode or not mode.strip():
            mode = distinct_modes[0] if distinct_modes else "Market Research"

        # Semantic Role Resolution
        resolved_role = role
        role_similarity = 1.0
        if self.role_resolver:
            resolved_role, role_similarity = await self.role_resolver.resolve_role(role, distinct_roles)

        # Semantic Mode Resolution
        resolved_mode = mode
        mode_similarity = 1.0
        if self.mode_resolver:
            resolved_mode, mode_similarity = await self.mode_resolver.resolve_mode(mode, distinct_modes)

        # Generate temporary embedding for the user prompt
        emb_start = time.perf_counter()
        try:
            prompt_embedding = self.embedding_service.generate_for_prompt(prompt)
        except Exception as exc:
            logger.exception("Failed to generate embedding for prompt")
            raise EmbeddingGenerationError("Failed to generate prompt embedding.") from exc
        emb_time = time.perf_counter() - emb_start

        # Retrieve candidate templates with resolved role/mode
        db_start = time.perf_counter()
        try:
            if self.candidate_service:
                candidates = await self.candidate_service.get_candidate_templates(
                    session=session,
                    vector=prompt_embedding,
                    role=resolved_role,
                    mode=resolved_mode,
                    limit=settings.top_k_results * 5,
                )
            else:
                candidates = await self.repository.search_templates_with_vector(
                    session=session,
                    vector=prompt_embedding,
                    role=resolved_role,
                    mode=resolved_mode,
                    is_approved=True,
                    limit=settings.top_k_results * 5,
                )
        except Exception as exc:
            logger.exception("Database search failure in TemplateRetrievalService")
            raise DatabaseFailureError("Database failure occurred during template retrieval.") from exc
        db_time = time.perf_counter() - db_start

        if not candidates:
            raise NoTemplatesFoundError(f"No approved templates found matching role '{resolved_role}' and mode '{resolved_mode}'.")

        # Perform hierarchical ranking
        rank_start = time.perf_counter()
        ranked = self.ranking_service.rank_candidates(
            candidates=candidates,
            target_role=resolved_role,
            target_mode=resolved_mode,
        )
        rank_time = time.perf_counter() - rank_start

        # Verify similarity threshold on the top ranked template
        top_match = ranked[0]
        similarity_threshold = threshold if threshold is not None else settings.similarity_threshold
        if top_match["similarity_score"] < similarity_threshold:
            raise SimilarityBelowThresholdError(
                f"Top matched template similarity score ({top_match['similarity_score']:.4f}) "
                f"is below the threshold ({similarity_threshold:.4f})."
            )

        selected_temp = top_match["template"]

        # Log according to logging spec
        logger.info(
            "Original Role: %s | Resolved Role: %s | Role Similarity: %.4f | "
            "Original Mode: %s | Resolved Mode: %s | Mode Similarity: %.4f | "
            "Final Template: %s | Template Similarity: %.4f",
            original_role, resolved_role, role_similarity,
            original_mode, resolved_mode, mode_similarity,
            selected_temp.title, top_match["similarity_score"]
        )

        reason = (
            f"Selected template '{selected_temp.title}' (ID: {selected_temp.id}) "
            f"has the highest semantic similarity score ({top_match['similarity_score']:.4f})."
        )
        if selected_temp.is_featured:
            reason += " Template is marked as featured."
        if selected_temp.use_count > 0:
            reason += f" Template has been used {selected_temp.use_count} times."

        top_k = top_k if top_k is not None else settings.top_k_results
        alternatives = []
        for idx, item in enumerate(ranked[1:top_k]):
            alternatives.append({
                "template_id": str(item["template"].id),
                "title": item["template"].title,
                "role": item["template"].role,
                "mode": item["template"].mode,
                "similarity_score": item["similarity_score"],
                "rank": idx + 2,
            })

        total_time = time.perf_counter() - total_start

        return {
            "selected_template": {
                "id": str(selected_temp.id),
                "title": selected_temp.title,
                "description": selected_temp.description,
                "body": selected_temp.body,
                "role": selected_temp.role,
                "mode": selected_temp.mode,
                "category": selected_temp.category,
                "tags": selected_temp.tags,
                "is_featured": selected_temp.is_featured,
                "use_count": selected_temp.use_count,
            },
            "similarity_score": top_match["similarity_score"],
            "selection_reason": reason,
            "alternative_templates": alternatives,
        }
