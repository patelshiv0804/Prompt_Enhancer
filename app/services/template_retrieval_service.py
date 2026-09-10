from __future__ import annotations

import logging
import time
from typing import Any, Optional
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


def _find_exact_match(value: Optional[str], candidates: list[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    normalized = value.strip().lower()
    for candidate in candidates:
        if candidate.strip().lower() == normalized:
            return candidate
    return None


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

        original_role = role
        original_mode = mode
        role_similarity = 1.0
        mode_similarity = 1.0

        # ── ROLE RESOLUTION ──────────────────────────────────────────────────────
        # Strategy:
        #   1. User provided role AND it has an exact match in DB → use it directly, skip all inference.
        #   2. User provided role but NO exact match (e.g. "general", a typo, or a stale value)
        #      → treat as if role was never provided → run full inference chain.
        #   3. Role is absent → run full inference chain.
        #
        # role_was_explicit = True means the user deliberately chose a valid DB role/mode.
        # When BOTH are explicit, the similarity threshold check is skipped — we just return
        # the best available template in that category without second-guessing the user's choice.
        #
        # NOTE: "general" and "auto" are NEVER treated as explicit even if they appear in the DB.
        # They signal "let the system decide" — forcing a similarity bypass would reproduce the
        # original hallucination bug where the Universal General Template was always selected.
        _NON_EXPLICIT_ROLES: frozenset[str] = frozenset({"general", "auto", ""})
        inferred_mode: None | str = None  # may be set by intent analysis below, reused for mode block
        role_was_explicit = False
        mode_was_explicit = False

        role_is_explicit_candidate = (
            bool(role and role.strip())
            and role.strip().lower() not in _NON_EXPLICIT_ROLES
        )
        exact_role = _find_exact_match(role, distinct_roles) if role_is_explicit_candidate else None

        if exact_role:
            # ✅ Exact match — user-selected value is valid, use it directly.
            resolved_role = exact_role
            role_was_explicit = True
            logger.info("Role exact match in DB, using directly: '%s'", resolved_role)
        else:
            # ❌ No exact match OR role absent — run full inference chain.
            if role and role.strip():
                logger.info(
                    "Role '%s' provided but not found in DB. Falling back to inference.", role
                )
            inferred_role: None | str = None
            if self.intent_service:
                inferred = await self.intent_service.analyze_intent(
                    prompt=prompt,
                    variables=variables,
                    provided_role=None,       # treat as absent so LLM reasons from the prompt
                    provided_mode=mode,
                    distinct_roles=distinct_roles,
                    distinct_modes=distinct_modes,
                )
                inferred_role = inferred.get("inferred_role")
                inferred_mode = inferred.get("inferred_mode")

            inferred_role_val = inferred_role if (inferred_role and inferred_role.strip()) else None
            if not inferred_role_val:
                inferred_role_val = distinct_roles[0] if distinct_roles else "Marketer"

            exact_inferred_role = _find_exact_match(inferred_role_val, distinct_roles)
            if exact_inferred_role:
                resolved_role = exact_inferred_role
            elif self.role_resolver:
                resolved_role, role_similarity = await self.role_resolver.resolve_role(
                    inferred_role_val, distinct_roles
                )
            else:
                resolved_role = inferred_role_val

            logger.info("Role inferred/resolved: '%s' → '%s'", inferred_role_val, resolved_role)
            inferred_mode = inferred_mode if (inferred_mode and inferred_mode.strip()) else None

        # ── LOAD ROLE-SCOPED MODES ────────────────────────────────────────────────
        role_modes = await self.repository.get_distinct_modes_for_role(session, resolved_role)
        if not role_modes:
            role_modes = distinct_modes

        # ── MODE RESOLUTION ──────────────────────────────────────────────────────
        # Same three-way strategy as role:
        #   1. Exact match in role-scoped modes → use directly.
        #   2. Provided but no exact match → fall back to inference.
        #   3. Absent → inference chain.
        exact_mode = _find_exact_match(mode, role_modes) if (mode and mode.strip()) else None

        if exact_mode:
            # ✅ Exact match.
            resolved_mode = exact_mode
            mode_was_explicit = True
            logger.info("Mode exact match in DB, using directly: '%s'", resolved_mode)
        else:
            # ❌ No exact match OR mode absent — run inference chain scoped to resolved role.
            if mode and mode.strip():
                logger.info(
                    "Mode '%s' provided but not found under role '%s'. Falling back to inference.",
                    mode, resolved_role,
                )
            # Reuse mode already inferred during role step if available.
            inferred_mode_val = inferred_mode if inferred_mode else None
            if not inferred_mode_val and self.intent_service:
                inferred = await self.intent_service.analyze_intent(
                    prompt=prompt,
                    variables=variables,
                    provided_role=resolved_role,
                    provided_mode=None,       # treat as absent so LLM reasons from the prompt
                    distinct_roles=[resolved_role],
                    distinct_modes=role_modes,
                )
                inferred_mode_val = inferred.get("inferred_mode")

            if not inferred_mode_val or not inferred_mode_val.strip():
                inferred_mode_val = role_modes[0] if role_modes else "Market Research"

            exact_inferred_mode = _find_exact_match(inferred_mode_val, role_modes)
            if exact_inferred_mode:
                resolved_mode = exact_inferred_mode
            elif self.mode_resolver:
                resolved_mode, mode_similarity = await self.mode_resolver.resolve_mode(
                    inferred_mode_val, role_modes
                )
            else:
                resolved_mode = inferred_mode_val

            logger.info("Mode inferred/resolved: '%s' → '%s'", inferred_mode_val, resolved_mode)

        # Generate embedding for the user prompt — cached when Redis is
        # available (same text always yields the same vector, so a cached
        # result is indistinguishable from a fresh one).
        emb_start = time.perf_counter()
        try:
            prompt_embedding = await self.embedding_service.generate_for_prompt_cached(prompt)
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
        user_made_explicit_selection = role_was_explicit and mode_was_explicit
        if not user_made_explicit_selection and top_match["similarity_score"] < similarity_threshold:
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
