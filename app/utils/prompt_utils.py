"""
Prompt utility functions — placeholder for Phase 2.
"""


def clean_prompt(text: str) -> str:
    """Remove excess whitespace from prompt text."""
    return " ".join(text.split())


def count_tokens_estimate(text: str) -> int:
    """Rough token count estimation (4 chars ≈ 1 token)."""
    return max(1, len(text) // 4)
