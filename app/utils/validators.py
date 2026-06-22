"""
Input validation helpers.
"""

import re

from app.core.constants import ALLOWED_AVATAR_EXTENSIONS


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_avatar_extension(filename: str) -> bool:
    """Check if file extension is allowed for avatars."""
    if not filename:
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_AVATAR_EXTENSIONS


def sanitize_display_name(name: str) -> str:
    """Sanitize display name — strip whitespace, limit length."""
    cleaned = name.strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned
