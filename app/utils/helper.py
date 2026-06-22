"""
Utility helper functions.
"""

from datetime import datetime, timezone
from uuid import UUID


def utc_now() -> datetime:
    """Get the current UTC timestamp."""
    return datetime.now(timezone.utc)


def format_uuid(value: UUID) -> str:
    """Format UUID to string."""
    return str(value)


def truncate_string(value: str, max_length: int = 100) -> str:
    """Truncate a string to max_length with ellipsis."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."
