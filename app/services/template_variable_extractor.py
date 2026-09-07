from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.services.llm.base import BaseLLMProvider
from app.services.prompt_sanitizer import neutralize_delimiters

logger = logging.getLogger("promptiq.template_variable_extractor")


class TemplateVariableExtractor:
    """
    TemplateVariableExtractor inspects template definitions and dynamically
    infers/extracts appropriate variable values from the user's raw prompt
    using a fast structured LLM call.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    def parse_template_variables(self, template_body: str) -> dict[str, str]:
        """
        Parse declared variables and their descriptions from the template body,
        as well as discovering any {PLACEHOLDER} tokens.

        Returns a mapping of {VARIABLE_NAME: description}.
        Always excludes 'REQUEST' as it maps directly to the user's raw prompt.
        """
        variables: dict[str, str] = {}

        # 1. Parse declared variables from the "Variables" block if present
        # Format: VARIABLE_NAME = [description]
        var_block_match = re.search(
            r"Variables\s*\n(.*?)(?:\n\s*(?:The Meta-Prompt|Step 1|Output Instructions|\n\n)|\Z)",
            template_body,
            re.DOTALL | re.IGNORECASE,
        )
        if var_block_match:
            block_text = var_block_match.group(1)
            for line in block_text.splitlines():
                line = line.strip()
                match = re.match(r"^([A-Z0-9_]+)\s*=\s*(.+)$", line)
                if match:
                    var_name = match.group(1).strip().upper()
                    desc = match.group(2).strip().strip("[]")
                    if var_name != "REQUEST":
                        variables[var_name] = desc

        # 2. Also find all placeholders {VAR_NAME} in the entire template body
        placeholders = re.findall(r"\{([A-Z0-9_]+)\}", template_body)
        for ph in set(placeholders):
            ph_upper = ph.strip().upper()
            if ph_upper != "REQUEST" and ph_upper not in variables:
                variables[ph_upper] = f"Value for {ph_upper}"

        return variables

    async def extract_variables(
        self,
        prompt: str,
        template_body: str,
        user_variables: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """
        Extract variable values from the user prompt for the given template.
        Any variables already provided explicitly in user_variables will not be overwritten.
        """
        if not prompt or not prompt.strip() or not template_body or not template_body.strip():
            return {}

        try:
            declared_vars = self.parse_template_variables(template_body)
            if not declared_vars:
                logger.debug("No extractable variables found in template body.")
                return {}

            # Filter out variables already supplied by caller
            normalized_user_vars = {
                k.strip().upper(): v
                for k, v in (user_variables or {}).items()
                if v is not None and str(v).strip()
            }

            needed_vars = {
                k: desc
                for k, desc in declared_vars.items()
                if k not in normalized_user_vars
            }

            if not needed_vars:
                logger.debug("All template variables already supplied by user.")
                return {}

            # Construct targeted extraction prompt
            var_specs = "\n".join(
                f"- {name}: {desc}" for name, desc in needed_vars.items()
            )

            extraction_prompt = (
                "You are an expert prompt-engineering assistant. Extract or infer specific values "
                "for the template variables below based solely on the user's raw prompt.\n\n"
                f"User Prompt:\n<<<\n{prompt.strip()}\n>>>\n\n"
                f"Template Variables to extract:\n{var_specs}\n\n"
                "Instructions:\n"
                "1. Extract or deduce the most accurate, contextually relevant value for each variable directly from the user's prompt.\n"
                "2. For LANGUAGE, default to 'English' unless another language is specified.\n"
                "3. If a variable represents existing assets, prior data, or constraints and none are mentioned in the prompt, set it to 'N/A' (or 'none' if required by the description).\n"
                "4. Provide concise, clear values without unnecessary boilerplate.\n"
                "5. Return ONLY a valid JSON object mapping each variable name to its string value.\n"
            )

            logger.info("Extracting %d template variables via LLM", len(needed_vars))
            
            try:
                res = await self.llm_provider.generate(
                    prompt=extraction_prompt,
                    max_tokens=300,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
            except Exception as e:
                logger.warning("Generation with json_object format failed, retrying without: %s", e)
                res = await self.llm_provider.generate(
                    prompt=extraction_prompt,
                    max_tokens=300,
                    temperature=0.1,
                )

            raw_text = res.text.strip()
            
            # Robust JSON extraction
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                parsed_json = json.loads(match.group(0))
            else:
                parsed_json = json.loads(raw_text)

            if not isinstance(parsed_json, dict):
                logger.warning("LLM returned non-dict JSON for variable extraction: %s", raw_text)
                return {}

            # Normalize and sanitize extracted values
            result: dict[str, str] = {}
            for k, v in parsed_json.items():
                norm_key = str(k).strip().upper()
                if norm_key in needed_vars and v is not None:
                    str_val = str(v).strip()
                    # Sanitize prompt injection / delimiter attacks
                    result[norm_key] = neutralize_delimiters(str_val)

            logger.info("Successfully extracted %d variables: %s", len(result), list(result.keys()))
            return result

        except Exception as exc:
            # Fault tolerance: never break prompt enhancement if variable extraction encounters an issue
            logger.warning("Variable extraction encountered an error; falling back to defaults: %s", exc)
            return {}
