from __future__ import annotations

import json
import logging
from typing import Any

from app.core import redis_client
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.prompt_sanitizer import neutralize_delimiters

logger = logging.getLogger("promptiq.prompt_classification")

# Keywords that reliably signal deep enhancement without an LLM call
_DEEP_KEYWORDS = frozenset([
    "plan", "strategy", "architecture", "system", "comprehensive",
    "detailed", "step-by-step", "roadmap", "framework", "in-depth",
])

# The user prompt is appended via safe string concatenation in classify() —
# NOT via .format() — to prevent delimiter or curly-brace injection.
# [PROMPT START] / [PROMPT END] labels cannot be collapsed by the sanitizer
# (unlike <<< / >>> which are stripped by neutralize_delimiters), so they
# cannot be forged by a user prompt that contains those exact strings.
_CLASSIFIER_PROMPT_HEADER = (
    "You are an expert prompt engineer. Classify the complexity of the user prompt below "
    "and decide how deeply it needs to be enhanced.\n\n"
    "Rules:\n"
    "- minimal: prompt is already clear and specific; only light touch-ups needed.\n"
    "- standard: prompt has good intent but lacks role, context, format, or constraints.\n"
    "- deep: prompt is vague, multi-part, strategic, or requires exhaustive restructuring.\n\n"
    "Respond ONLY with a valid JSON object — no markdown, no extra text:\n"
    '{"level": "minimal"|"standard"|"deep", "reason": "<one sentence>"}\n\n'
    "User prompt:\n"
    "[PROMPT START]\n"
)

_FALLBACK_RESULT: dict[str, str] = {"level": "standard", "reason": "Default depth applied."}


class PromptClassificationService:
    """
    Classifies a raw prompt into minimal / standard / deep enhancement depth.

    Static guards handle the extreme cases cheaply (no LLM call).
    The LLM is only invoked for ambiguous mid-range prompts, at temperature=0.0
    for maximum determinism and with a tight token budget (~120 tokens).
    On any failure the service silently returns "standard" so the main
    enhancement flow is never blocked.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def classify(self, prompt: str) -> dict[str, str]:
        """
        Returns a dict with keys:
          - level: "minimal" | "standard" | "deep"
          - reason: short human-readable explanation
        Never raises — falls back to _FALLBACK_RESULT on any error.
        """
        if not prompt or not prompt.strip():
            return _FALLBACK_RESULT

        stripped = prompt.strip()

        # ── Static guards (free, no LLM) ──────────────────────────────────
        if len(stripped) < 60:
            logger.debug("Classification static guard: minimal (short prompt)")
            return {"level": "minimal", "reason": "Prompt is short and focused."}

        if len(stripped) > 800:
            logger.debug("Classification static guard: deep (long prompt)")
            return {"level": "deep", "reason": "Prompt is long and likely complex."}

        lower = stripped.lower()
        if any(kw in lower for kw in _DEEP_KEYWORDS):
            logger.debug("Classification static guard: deep (keyword match)")
            return {"level": "deep", "reason": "Prompt contains strategic or complex keywords."}

        # ── LLM classification (Redis-cached) ──────────────────────────────
        # temperature=0.0 makes this deterministic — the same prompt always
        # yields the same level — so a cached answer is byte-identical to a
        # fresh one and nothing about the user's result changes. (Contrast the
        # enhancement call at temperature 0.3, where that variation is the
        # whole point of the Regenerate button and must never be cached.)
        cache_key = redis_client.make_key(
            redis_client.NS_CLASSIFY, redis_client.hash_text(stripped)
        )
        cached = await redis_client.get_json(cache_key)
        if isinstance(cached, dict) and cached.get("level") in ("minimal", "standard", "deep"):
            logger.debug("Classification cache hit")
            return cached

        try:
            # Sanitize delimiter runs before interpolation so the user cannot
            # escape the [PROMPT START]/[PROMPT END] fence via <<<, >>>, etc.
            safe_stripped = neutralize_delimiters(stripped)
            # Safe concatenation: avoids .format() so {curly_braces} in the
            # prompt cannot be interpreted as Python format-string keys.
            classifier_prompt = (
                _CLASSIFIER_PROMPT_HEADER
                + safe_stripped
                + "\n[PROMPT END]"
            )
            result = await self.llm_provider.generate(
                prompt=classifier_prompt,
                max_tokens=120,
                temperature=0.0,
            )
            parsed = self._parse(result.text)
        except Exception:
            logger.warning("Prompt classification failed; falling back to 'standard'", exc_info=True)
            return _FALLBACK_RESULT

        # Never cache the fallback: a transient LLM hiccup or an unparseable
        # reply would otherwise be pinned as this prompt's answer for a day.
        if parsed is not _FALLBACK_RESULT:
            await redis_client.set_json(
                cache_key, parsed, ttl=settings.redis_ttl_classification
            )
        return parsed

    # ── Internal helpers ───────────────────────────────────────────────────

    def _parse(self, text: str) -> dict[str, str]:
        """Strip markdown fences and parse the classifier JSON safely."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data: Any = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Classifier returned non-JSON: %s", cleaned[:200])
            return _FALLBACK_RESULT

        if not isinstance(data, dict):
            return _FALLBACK_RESULT

        level = data.get("level", "")
        if level not in ("minimal", "standard", "deep"):
            logger.warning("Classifier returned unknown level '%s'; defaulting to standard", level)
            level = "standard"

        reason = str(data.get("reason", "")).strip() or _FALLBACK_RESULT["reason"]
        return {"level": level, "reason": reason}
