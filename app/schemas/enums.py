from __future__ import annotations

from enum import Enum


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    GOOGLE_PALM = "google_palm"
    MISTRAL = "mistral"
    OTHER = "other"


class TemplateMode(str, Enum):
    COMPLETION = "completion"
    CONVERSATION = "conversation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    OTHER = "other"


class VersionType(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    RESTORED = "restored"


class PromptGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"
