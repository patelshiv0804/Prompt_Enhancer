from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class PromptTitleService:
    """Service to generate concise, high-signal 2-5 word chat titles (ChatGPT style)

    using the configured LLM provider, with graceful fallback to the original prompt.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    def fallback_title(self, prompt: str, max_length: int = 60) -> str:
        """Fallback title matching the existing behavior (using the prompt itself)."""
        clean = (prompt or "").strip().replace("\n", " ")
        clean = re.sub(r"\s+", " ", clean)
        if len(clean) > max_length:
            return clean[:max_length].strip()
        return clean or "Untitled Prompt"

    def _clean_title(self, raw_title: str) -> str:
        """Cleans quotation marks, backticks, prefixes, and trailing punctuation."""
        title = raw_title.strip()
        # Remove common LLM prefixes (e.g. "Title: ...")
        title = re.sub(r"^(?:Title|Topic):\s*", "", title, flags=re.IGNORECASE)
        # Strip surrounding quotes and backticks
        title = title.strip("\"'`* \t\r\n")
        # Remove trailing periods
        title = title.rstrip(".!?")
        # Collapse multiple spaces
        title = re.sub(r"\s+", " ", title).strip()
        return title

    async def generate_title(self, prompt: str) -> str:
        """Generates a smart 2-5 word title summarizing the prompt.

        Falls back to the prompt itself if the LLM call fails.
        """
        if not prompt or not prompt.strip():
            return "Untitled Prompt"

        title_prompt = (
            "You are ChatGPT's chat title generator. Generate a concise 2 to 4 word chat title "
            "that summarizes what the user is requesting in their prompt.\n\n"
            "Rules to match ChatGPT chat titles:\n"
            "1. Focus on the user's intent and request (e.g. Action Verb + Specific Subject + Format).\n"
            "2. Never write a poetic story summary (do NOT write 'Martian Garden Discovery' or 'A Journey to Mars'). "
            "Instead, state the user's task (e.g. 'Write Mars Garden Fiction' or 'Improve Greenery Image').\n"
            "3. Keep it strictly between 2 and 4 words.\n"
            "4. Match these real ChatGPT title patterns:\n"
            "   - 'write a cinematic short about an astronaut who discovers a garden on mars. make it emotional.' -> 'Write Mars Garden Fiction'\n"
            "   - 'i want to improve the greenry in this image' -> 'Improve Greenery Image'\n"
            "   - 'generate an ad prompt for aure saas' -> 'Generate AURE Ad Prompt'\n"
            "   - 'create a tech advertisement for wireless earbuds' -> 'Create Tech Advertisement'\n"
            "   - 'tips for car breakdown safety on a highway' -> 'Car Breakdown Safety'\n"
            "   - 'how to adjust interface layout in react' -> 'Interface Layout Adjustment'\n"
            "   - 'design a modern login page for my saas web app' -> 'Design SaaS Login'\n\n"
            "5. Output ONLY the 2-4 word title in Title Case. Do NOT include quotation marks, labels, or periods.\n\n"
            f"User Prompt:\n{prompt.strip()[:600]}\n\n"
            "Title:"
        )

        try:
            res = await self.llm_provider.generate(
                prompt=title_prompt,
                max_tokens=25,
                temperature=0.2,
            )
            raw = res.text if hasattr(res, "text") else str(res)
            cleaned = self._clean_title(raw)
            if cleaned and 3 <= len(cleaned) <= 80:
                words = cleaned.split()
                if 1 <= len(words) <= 8:
                    logger.info("Generated AI chat title: '%s' for prompt: '%s...'", cleaned, prompt[:40])
                    return cleaned
        except Exception as exc:
            logger.warning("AI title generation failed (%s), falling back to original prompt.", exc)

        return self.fallback_title(prompt)
