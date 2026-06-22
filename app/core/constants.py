"""
Application-wide constants and enums.
"""

from enum import Enum


class Plan(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class Theme(str, Enum):
    """UI theme options."""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class DefaultModel(str, Enum):
    """Available AI models."""
    CHATGPT = "chatgpt"
    GPT4 = "gpt-4"
    GPT5 = "gpt-5"
    CLAUDE_SONNET = "claude-sonnet-4.5"
    CLAUDE_OPUS = "claude-opus-4"
    GEMINI_PRO = "gemini-pro"
    GEMINI_FLASH = "gemini-flash"
    GROQ_LLAMA = "groq-llama"


class DefaultMode(str, Enum):
    """Prompt mode categories."""
    GENERAL = "general"
    YOUTUBE_SHORTS = "youtube-shorts"
    BLOG = "blog"
    RESEARCH = "research"
    STORYTELLING = "storytelling"
    CODE = "code"
    MARKETING = "marketing"
    EMAIL = "email"


# ── Default settings values ─────────────────────────────
DEFAULT_SETTINGS = {
    "theme": Theme.SYSTEM.value,
    "default_mode": DefaultMode.GENERAL.value,
    "default_model": DefaultModel.CHATGPT.value,
    "show_diff_by_default": True,
    "auto_detect_intent": True,
}

# ── File upload constraints ──────────────────────────────
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_AVATAR_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
