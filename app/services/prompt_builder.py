from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("promptiq.prompt_builder")

# Maps an enhancement depth level to a clear directive for the LLM.
_DEPTH_INSTRUCTIONS: dict[str, str] = {
    "minimal": (
        "Apply only light improvements: fix grammar, tighten clarity, and add minimal structure. "
        "Preserve the user's original wording and intent as closely as possible."
    ),
    "standard": (
        "Enhance with standard prompt-engineering depth: assign a clear role, add context, "
        "specify output format, and include relevant constraints. Default enhancement level."
    ),
    "deep": (
        "Apply full prompt-engineering depth: multi-layered role definition, step-by-step "
        "reasoning chain, exhaustive context and constraints, few-shot examples where helpful, "
        "and a detailed output schema. Leave no ambiguity."
    ),
}


class PromptBuilder:
    """
    PromptBuilder compiles standard system instructions, role, mode,
    and the rendered template into a unified, deterministic prompt.
    """

    DEFAULT_SYSTEM_INSTRUCTIONS = (
        "You are a professional Prompt Enhancement Engine. "
        "Your sole task is to transform the user's raw prompt into an optimized, structured prompt based on the provided instructions. "
        "Crucially, you must NEVER answer, execute, or solve the user's request. "
        "Instead, your output MUST be the newly constructed, enhanced prompt itself, ready for execution. "
        "Output ONLY the final enhanced prompt. Do not include introductory text, conversation, or markdown code blocks."
    )

    def build_final_prompt(
        self,
        role: str,
        mode: str,
        rendered_template: str,
        system_instructions: Optional[str] = None,
        style_attributes: Optional[dict] = None,
        enhancement_level: str = "standard",
    ) -> str:
        logger.info("Building final prompt for the configured LLM (level=%s)", enhancement_level)
        sys_inst = system_instructions or self.DEFAULT_SYSTEM_INSTRUCTIONS

        # Assemble prompt components deterministically
        parts = [
            f"=== SYSTEM INSTRUCTIONS ===\n{sys_inst.strip()}",
            f"=== TARGET PROFILE ===\nRole: {role.strip()}\nMode: {mode.strip()}",
        ]

        # Inject depth directive so the LLM knows how much restructuring to apply
        depth_text = _DEPTH_INSTRUCTIONS.get(enhancement_level, _DEPTH_INSTRUCTIONS["standard"])
        parts.append(f"=== ENHANCEMENT DEPTH ===\n{depth_text}")

        if style_attributes:
            import json
            attr_str = json.dumps(style_attributes, indent=2)
            parts.append(f"=== STYLE PROFILE ATTRIBUTES ===\n{attr_str}")

        parts.append(f"=== RETRIEVED ENHANCEMENT TEMPLATE ===\n{rendered_template.strip()}")

        final_prompt = "\n\n".join(parts)
        logger.debug("Compiled prompt length: %d chars", len(final_prompt))
        return final_prompt
