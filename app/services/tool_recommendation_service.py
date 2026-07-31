"""
tool_recommendation_service.py — AI Tool Recommendation Engine
================================================================
Recommends the best AI tools for a user's task by matching their
mode, role, and/or prompt content against the static tool ranking table.

Matching & Resolution Rules:
  1. Evaluate prompt match (exact → alias → semantic → keyword).
  2. Evaluate explicit signal match (mode or role, via exact → alias → semantic → keyword).
  3. Resolution:
     a) If BOTH prompt and mode/role match:
        - If they agree → return "consensus".
        - If they disagree → PROMPT WINS (prompt represents explicit task intent).
     b) If only prompt matches → return prompt match.
     c) If only mode/role matches → return mode/role match.
     d) If neither matches → return fallback ("General Chat").
"""

from __future__ import annotations

import logging
from typing import Optional

from app.data.tool_rankings import TOOL_RANKINGS, DEFAULT_RECOMMENDATION
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("promptiq.tool_recommendation")

# Cosine similarity threshold — below this we treat as "no match"
SIMILARITY_THRESHOLD = 0.55


class ToolRecommendationService:
    """Recommends AI tools based on the user's mode, role, and prompt content."""

    # Class-level cache so embeddings are computed once across all instances
    _task_embeddings: Optional[list[tuple[str, int, list[float]]]] = None

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service

    # ── Public API ────────────────────────────────────────────────────

    async def recommend(
        self,
        prompt: str,
        mode: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict:
        """
        Recommend AI tools based on prompt, mode, and role with prompt-priority resolution.
        """
        # Ensure embedding cache is ready
        self._ensure_embeddings_cached()

        # 1. Resolve prompt match (highest intent signal)
        prompt_match = self._resolve_single_text(prompt, text_type="prompt")

        # 2. Resolve explicit signal match (mode first, then role)
        explicit_match = None
        if mode and mode.strip():
            explicit_match = self._resolve_single_text(mode, text_type="mode")
        if not explicit_match and role and role.strip():
            explicit_match = self._resolve_single_text(role, text_type="role")

        # 3. Dual-Signal Priority Resolution
        if prompt_match and explicit_match:
            if prompt_match["task"] == explicit_match["task"]:
                # They agree — consensus
                best_confidence = max(prompt_match["confidence"], explicit_match["confidence"])
                return self._build_result(
                    task=prompt_match["task"],
                    match_type="consensus",
                    confidence=best_confidence,
                )
            else:
                # They DISAGREE (e.g. role="Coding", prompt="Frontend Landing Page")
                # PROMPT WINS because prompt reflects actual specific intent
                logger.info(
                    "Signal disagreement: prompt matched '%s', explicit matched '%s'. Prompt wins.",
                    prompt_match["task"], explicit_match["task"],
                )
                return self._build_result(
                    task=prompt_match["task"],
                    match_type=prompt_match["match_type"],
                    confidence=prompt_match["confidence"],
                )

        if prompt_match:
            return self._build_result(
                task=prompt_match["task"],
                match_type=prompt_match["match_type"],
                confidence=prompt_match["confidence"],
            )

        if explicit_match:
            return self._build_result(
                task=explicit_match["task"],
                match_type=explicit_match["match_type"],
                confidence=explicit_match["confidence"],
            )

        # 4. Default Fallback
        return self.get_fallback()

    def get_fallback(self) -> dict:
        """Return the default General Chat recommendation."""
        return self._build_result(
            task=DEFAULT_RECOMMENDATION["task"],
            match_type="fallback",
            confidence=0.0,
        )

    # ── Single-Text Match Resolver (Exact → Alias → Semantic → Keyword) ──

    def _resolve_single_text(self, text: str, text_type: str) -> Optional[dict]:
        """Resolve a single text input across exact, alias, semantic, and keyword matchers."""
        if not text or not text.strip():
            return None

        # 1. Exact match
        exact = self._match_exact(text)
        if exact:
            exact["match_type"] = f"{text_type}_exact" if text_type != "prompt" else "exact"
            return exact

        # 2. Alias match
        alias = self._match_alias(text)
        if alias:
            alias["match_type"] = f"{text_type}_alias" if text_type != "prompt" else "alias"
            return alias

        # 3. Semantic match (if embeddings cached)
        semantic = self._semantic_match(text)
        if semantic:
            semantic["match_type"] = f"{text_type}_semantic" if text_type != "prompt" else "prompt_semantic"
            return semantic

        # 4. Keyword substring match
        keyword = self._keyword_match(text)
        if keyword:
            keyword["match_type"] = f"{text_type}_keyword" if text_type != "prompt" else "prompt_keyword"
            return keyword

        return None

    # ── Matchers ──────────────────────────────────────────────────────

    def _match_exact(self, text: str) -> Optional[dict]:
        text_lower = text.strip().lower()
        for entry in TOOL_RANKINGS:
            if entry["task"].lower() == text_lower:
                return {"task": entry["task"], "confidence": 1.0}
        return None

    def _match_alias(self, text: str) -> Optional[dict]:
        text_lower = text.strip().lower()
        for entry in TOOL_RANKINGS:
            for alias in entry["aliases"]:
                if alias.lower() == text_lower:
                    return {"task": entry["task"], "confidence": 1.0}
        return None

    def _keyword_match(self, text: str) -> Optional[dict]:
        text_lower = text.strip().lower()
        best_entry = None
        longest_match_len = 0

        for entry in TOOL_RANKINGS:
            if entry["task"] == "General Chat":
                continue

            if entry["task"].lower() in text_lower:
                match_len = len(entry["task"])
                if match_len > longest_match_len:
                    longest_match_len = match_len
                    best_entry = entry

            for alias in entry["aliases"]:
                if alias.lower() in text_lower:
                    match_len = len(alias)
                    if match_len > longest_match_len:
                        longest_match_len = match_len
                        best_entry = entry

        if best_entry:
            return {"task": best_entry["task"], "confidence": 0.8}
        return None

    # ── Semantic Matching ─────────────────────────────────────────────

    def _semantic_match(self, text: str) -> Optional[dict]:
        if not text or not text.strip() or self._task_embeddings is None:
            return None

        try:
            text_emb = self.embedding_service.generate_for_prompt(text)
            best_task = None
            best_score = -1.0

            for task_label, idx, task_emb in self._task_embeddings:
                similarity = sum(x * y for x, y in zip(text_emb, task_emb))
                if similarity > best_score:
                    best_score = similarity
                    best_task = task_label

            if best_score >= SIMILARITY_THRESHOLD:
                return {
                    "task": best_task,
                    "confidence": round(best_score, 4),
                }
            return None

        except Exception as exc:
            logger.warning("Semantic matching skipped: %s", exc)
            return None

    # ── Embedding Cache ───────────────────────────────────────────────

    def _ensure_embeddings_cached(self) -> None:
        if ToolRecommendationService._task_embeddings is not None:
            return

        try:
            logger.info("Pre-computing embeddings for %d tool ranking tasks...", len(TOOL_RANKINGS))
            cache = []
            for idx, entry in enumerate(TOOL_RANKINGS):
                task_label = entry["task"]
                emb = self.embedding_service.generate_for_prompt(task_label)
                cache.append((task_label, idx, emb))

            ToolRecommendationService._task_embeddings = cache
            logger.info("Tool ranking embeddings cached successfully.")
        except Exception as exc:
            logger.warning("Could not pre-compute embeddings (offline/no model): %s", exc)
            ToolRecommendationService._task_embeddings = None

    # ── Result Builder ────────────────────────────────────────────────

    def _build_result(self, task: str, match_type: str, confidence: float) -> dict:
        entry = self._find_entry(task)
        return {
            "matched_task": entry["task"],
            "match_type": match_type,
            "match_confidence": confidence,
            "tools": [
                {"name": entry["rank_1"], "rank": 1},
                {"name": entry["rank_2"], "rank": 2},
                {"name": entry["rank_3"], "rank": 3},
            ],
        }

    @staticmethod
    def _find_entry(task: str) -> dict:
        for entry in TOOL_RANKINGS:
            if entry["task"] == task:
                return entry
        return DEFAULT_RECOMMENDATION
