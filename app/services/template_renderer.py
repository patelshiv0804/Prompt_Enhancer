from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.exceptions import TemplateRenderException

logger = logging.getLogger("promptiq.template_renderer")


class TemplateRenderer:
    """
    TemplateRenderer is responsible for detecting variables, validating inputs,
    and rendering placeholder strings (e.g. {REQUEST}) inside template bodies.
    """

    def render(
        self,
        template_body: str,
        user_prompt: str,
        variables: Optional[dict[str, str]] = None,
    ) -> str:
        logger.info("Rendering template placeholders")
        if variables is None:
            variables = {}

        # Normalize key names to uppercase for robust matching
        normalized_vars = {k.strip().upper(): v for k, v in variables.items()}

        # Core required variable: REQUEST must be the user's prompt
        if "REQUEST" not in normalized_vars:
            if not user_prompt or not user_prompt.strip():
                raise TemplateRenderException("Required template variable REQUEST is missing or empty.")
            normalized_vars["REQUEST"] = user_prompt

        # Find all placeholders matching uppercase keys {VAR_NAME}
        placeholders = re.findall(r"\{([A-Z_0-9]+)\}", template_body)
        unique_placeholders = list(set(placeholders))
        logger.debug("Found placeholders in template body: %s", unique_placeholders)

        rendered_body = template_body
        for ph in unique_placeholders:
            val = normalized_vars.get(ph)
            if val is None:
                # Apply fallback defaults for missing optional variables
                if ph == "REQUEST":
                    raise TemplateRenderException("Required variable REQUEST is unresolved.")
                elif ph == "LANGUAGE":
                    val = "English"
                    logger.debug("Applying default value for {LANGUAGE} -> 'English'")
                else:
                    val = "N/A"
                    logger.debug("Applying default fallback value for {%s} -> 'N/A'", ph)
            
            rendered_body = rendered_body.replace(f"{{{ph}}}", val)

        # Sanity check: Ensure no leftover unrendered placeholders remain in the prompt
        leftover = re.findall(r"\{([A-Z_0-9]+)\}", rendered_body)
        if leftover:
            raise TemplateRenderException(f"Unresolved placeholders found in rendered template: {list(set(leftover))}")

        logger.info("Template rendering completed successfully.")
        return rendered_body
