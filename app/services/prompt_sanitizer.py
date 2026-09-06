from __future__ import annotations

"""Neutralizes structural delimiters in user-derived text before it is
interpolated into LLM prompts.

The prompt pipeline frames trusted sections with markers such as
``=== SYSTEM INSTRUCTIONS ===``, ``<<< ... >>>`` fences, and markdown code
fences. Any user-controlled string that reaches those prompts (the raw prompt,
template variables, role/mode labels) could otherwise forge a fake section
boundary and smuggle instructions into a "trusted" section. Collapsing runs of
the delimiter characters makes forged markers impossible while leaving normal
prose untouched.

This is intentionally NOT a blacklist of injection phrases — phrasing filters
are trivially bypassed. The real defense is role separation (system vs user
messages); this module only removes the structural ambiguity.
"""

import re
from typing import Optional

# Each pattern collapses a run of 3+ delimiter chars down to 2, which can never
# match the 3-char-minimum framing markers used by the prompt builders.
_DELIMITER_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"={3,}"), "=="),
    (re.compile(r"<{3,}"), "<<"),
    (re.compile(r">{3,}"), ">>"),
    (re.compile(r"`{3,}"), "``"),
]


def neutralize_delimiters(text: Optional[str]) -> str:
    """Collapse delimiter runs in a single user-derived string."""
    if not text:
        return "" if text is None else text
    for pattern, replacement in _DELIMITER_RULES:
        text = pattern.sub(replacement, text)
    return text


def sanitize_variables(variables: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
    """Sanitize every value of a template-variables mapping (keys untouched)."""
    if not variables:
        return variables
    return {k: neutralize_delimiters(v) if isinstance(v, str) else v for k, v in variables.items()}
