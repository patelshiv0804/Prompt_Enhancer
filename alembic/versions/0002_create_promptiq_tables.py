"""create core PromptIQ tables

Revision ID: 0002_create_promptiq_tables
Revises: 0001_create_pgvector_extension
Create Date: 2026-06-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0002_create_promptiq_tables"
down_revision = "0001_create_pgvector_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_profiles_email", "profiles", ["email"], unique=True)

    op.create_table(
        "ai_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_analysis", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_optimization", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "model_name", name="uq_ai_models_provider_model_name"),
    )
    op.create_index("ix_ai_models_is_active", "ai_models", ["is_active"])

    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("ai_model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_templates_mode", "templates", ["mode"])
    op.create_index("ix_templates_category", "templates", ["category"])
    op.create_index("ix_templates_is_featured", "templates", ["is_featured"])
    op.create_index("ix_templates_is_approved", "templates", ["is_approved"])

    op.create_table(
        "prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("original_prompt", sa.Text(), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("old_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("grade", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_prompts_user_id", "prompts", ["user_id"])
    op.create_index("ix_prompts_template_id", "prompts", ["template_id"])
    op.create_index("ix_prompts_ai_model_id", "prompts", ["ai_model_id"])
    op.create_index("ix_prompts_current_version_id", "prompts", ["current_version_id"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("prompt_id", "version_number", name="uq_prompt_versions_prompt_id_version_number"),
    )
    op.create_index("ix_prompt_versions_prompt_id", "prompt_versions", ["prompt_id"])
    op.create_index("ix_prompt_versions_prompt_id_version_number", "prompt_versions", ["prompt_id", "version_number"])

    op.create_foreign_key(
        "fk_prompts_current_version_id_prompt_versions",
        "prompts",
        "prompt_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_prompts_current_version_id_prompt_versions", "prompts", type_="foreignkey")
    op.drop_index("ix_prompt_versions_prompt_id_version_number", table_name="prompt_versions")
    op.drop_index("ix_prompt_versions_prompt_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_index("ix_prompts_current_version_id", table_name="prompts")
    op.drop_index("ix_prompts_ai_model_id", table_name="prompts")
    op.drop_index("ix_prompts_template_id", table_name="prompts")
    op.drop_index("ix_prompts_user_id", table_name="prompts")
    op.drop_table("prompts")
    op.drop_index("ix_templates_is_approved", table_name="templates")
    op.drop_index("ix_templates_is_featured", table_name="templates")
    op.drop_index("ix_templates_category", table_name="templates")
    op.drop_index("ix_templates_mode", table_name="templates")
    op.drop_table("templates")
    op.drop_index("ix_ai_models_is_active", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_index("ix_profiles_email", table_name="profiles")
    op.drop_table("profiles")
