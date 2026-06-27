

from sqlalchemy import JSON
from sqlalchemy import CheckConstraint
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Float,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlmodel import Field, Relationship, SQLModel
# pyrefly: ignore [missing-import]



class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, default=uuid4, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    email: str = Field(sa_column=Column(String(length=255), nullable=False, unique=True, index=True))
    full_name: Optional[str] = Field(default=None, sa_column=Column(String(length=255), nullable=True))
    display_name: Optional[str] = Field(default=None, sa_column=Column(String(length=255), nullable=True))
    avatar_url: Optional[str] = Field(default=None, sa_column=Column(String(length=512), nullable=True))
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )

    plan: str = Field(default="free", sa_column=Column(String, nullable=False, server_default=text("'free'")))
    onboarding_completed: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default=text("false")))
    deleted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    prompts: List["Prompt"] = Relationship(back_populates="profile")
    settings: Optional["UserSettings"] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    user: Optional["User"] = Relationship(back_populates="profile")


class AIModel(SQLModel, table=True):
    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_ai_models_provider_model_name"),
        Index("ix_ai_models_is_active", "is_active"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    provider: str = Field(sa_column=Column(String(length=100), nullable=False))
    model_name: str = Field(sa_column=Column(String(length=150), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    supports_analysis: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    supports_optimization: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )

    templates: List["Template"] = Relationship(back_populates="ai_model")
    prompts: List["Prompt"] = Relationship(back_populates="ai_model")


class Template(SQLModel, table=True):
    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_templates_mode", "mode"),
        Index("ix_templates_category", "category"),
        Index("ix_templates_is_featured", "is_featured"),
        Index("ix_templates_is_approved", "is_approved"),
        Index("ix_templates_ai_model_id", "ai_model_id"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    title: str = Field(sa_column=Column(String(length=255), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    body: str = Field(sa_column=Column(Text, nullable=False))
    mode: Optional[str] = Field(default=None, sa_column=Column(String(length=100), nullable=True))
    category: Optional[str] = Field(default=None, sa_column=Column(String(length=100), nullable=True))
    ai_model_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False)
    )
    tags: List[str] = Field(sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")))
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(384), nullable=True))
    is_featured: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_approved: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    use_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )

    ai_model: Optional[AIModel] = Relationship(back_populates="templates")
    prompts: List["Prompt"] = Relationship(back_populates="template")


class Prompt(SQLModel, table=True):
    __tablename__ = "prompts"
    __table_args__ = (
        Index("ix_prompts_user_id", "user_id"),
        Index("ix_prompts_template_id", "template_id"),
        Index("ix_prompts_ai_model_id", "ai_model_id"),
        Index("ix_prompts_current_version_id", "current_version_id"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    )
    template_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True),
    )
    ai_model_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True),
    )
    title: Optional[str] = Field(default=None, sa_column=Column(String(length=255), nullable=True))
    original_prompt: str = Field(sa_column=Column(Text, nullable=False))
    current_version_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey(
                "prompt_versions.id",
                ondelete="SET NULL",
                deferrable=True,
                initially="DEFERRED",
            ),
            nullable=True,
        ),
    )
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(384), nullable=True))
    total_score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    grade: Optional[str] = Field(default=None, sa_column=Column(String(length=16), nullable=True))

    profile: Optional[Profile] = Relationship(back_populates="prompts")
    template: Optional[Template] = Relationship(back_populates="prompts")
    ai_model: Optional[AIModel] = Relationship(back_populates="prompts")
    versions: List["PromptVersion"] = Relationship(
        back_populates="prompt",
        sa_relationship_kwargs={"foreign_keys": "[PromptVersion.prompt_id]"},
    )
    current_version: Optional["PromptVersion"] = Relationship(
        back_populates="current_for_prompt",
        sa_relationship_kwargs={"foreign_keys": "[Prompt.current_version_id]"},
    )


class PromptVersion(SQLModel, table=True):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version_number", name="uq_prompt_versions_prompt_id_version_number"),
        Index("ix_prompt_versions_prompt_id", "prompt_id"),
        Index("ix_prompt_versions_prompt_id_version_number", "prompt_id", "version_number"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    prompt_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    )
    version_number: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    version_type: Optional[str] = Field(default=None, sa_column=Column(String(length=100), nullable=True))
    content: str = Field(sa_column=Column(Text, nullable=False))
    change_summary: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    prompt: Optional[Prompt] = Relationship(
        back_populates="versions",
        sa_relationship_kwargs={"foreign_keys": "[PromptVersion.prompt_id]"},
    )
    current_for_prompt: Optional[Prompt] = Relationship(
        back_populates="current_version",
        sa_relationship_kwargs={"foreign_keys": "[Prompt.current_version_id]"},
    )
class StyleProfile(SQLModel, table=True):
    __tablename__ = "style_profiles"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    )
    user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), nullable=True)
    )
    name: str = Field(
        sa_column=Column(String(100), nullable=False)
    )
    type: str = Field(
        sa_column=Column(String(50), nullable=False)
    )
    attributes: dict = Field(
        sa_column=Column(JSON, nullable=False)
    )
    injection_template: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True)
    )
    is_active: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False, server_default=text("false"), nullable=False)
    )
    use_count: int = Field(
        default=0,
        sa_column=Column(Integer, default=0, server_default=text("0"), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('character', 'cinematic', 'art_style', 'environment', 'brand_voice')",
            name="valid_type_constraint"
        ),
    )
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    email: str = Field(sa_column=Column(String, unique=True, nullable=False, index=True))
    hashed_password: str = Field(sa_column=Column(String, nullable=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, default=True, nullable=False))
    is_verified: bool = Field(default=False, sa_column=Column(Boolean, default=False, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    profile: Optional["Profile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False),
    )
    user_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True, nullable=False),
    )
    theme: str = Field(default="system", sa_column=Column(String, nullable=False, server_default=text("'system'")))
    default_mode: str = Field(default="general", sa_column=Column(String, nullable=False, server_default=text("'general'")))
    default_model: str = Field(default="chatgpt", sa_column=Column(String, nullable=False, server_default=text("'chatgpt'")))
    show_diff_by_default: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))
    auto_detect_intent: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    profile: Optional["Profile"] = Relationship(back_populates="settings")
