from __future__ import annotations

import json
import logging
import re
from typing import Optional
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger("promptiq.intent_analysis")

class IntentAnalysisService:
    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def analyze_intent(
        self,
        prompt: str,
        variables: Optional[dict[str, str]] = None,
        provided_role: Optional[str] = None,
        provided_mode: Optional[str] = None,
        distinct_roles: Optional[list[str]] = None,
        distinct_modes: Optional[list[str]] = None,
    ) -> dict[str, Optional[str]]:
        logger.info("Analyzing intent for missing role or mode")
        
        roles_ctx = ", ".join(distinct_roles) if distinct_roles else "None specified"
        modes_ctx = ", ".join(distinct_modes) if distinct_modes else "None specified"

        llm_prompt = (
            "Analyze the user's input prompt and variables to infer their target professional/academic Role and target Mode of work.\n\n"
            f"User Prompt: {prompt}\n"
            f"Variables: {json.dumps(variables or {})}\n"
            f"Known Role (if provided): {provided_role or 'None'}\n"
            f"Known Mode (if provided): {provided_mode or 'None'}\n\n"
            f"Available target Roles to choose from: [{roles_ctx}]\n"
            f"Available target Modes to choose from: [{modes_ctx}]\n\n"
            "Return ONLY a JSON object with keys 'inferred_role' and 'inferred_mode'. Do not include any markdown formatting, backticks, or explanation. "
            "If a role or mode is already provided above, set the corresponding inferred value to that provided value. "
            "If you cannot infer a sensible role or mode, set the value to null."
        )

        try:
            res = await self.llm_provider.generate(llm_prompt, temperature=0.1)
            text = res.text.strip()
            
            # Extract JSON block robustly
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                data = json.loads(text)
                
            inferred_role = data.get("inferred_role")
            inferred_mode = data.get("inferred_mode")
            
            return {
                "inferred_role": inferred_role if inferred_role else provided_role,
                "inferred_mode": inferred_mode if inferred_mode else provided_mode,
            }
        except Exception as exc:
            logger.exception("Intent analysis failed, falling back to raw inputs")
            return {
                "inferred_role": provided_role,
                "inferred_mode": provided_mode,
            }
