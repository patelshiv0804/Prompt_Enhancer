"""create_user_activities_and_badges_tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-18 17:35:00.000000

Creates dedicated tables for:
1. `user_daily_activities` - Immutable daily telemetry ledger to track enhancement
   events by date. Decouples the activity calendar heatmap, active days, and streak
   tracking from user prompt deletions in the Vault.
2. `user_unlocked_badges` - Permanent achievement unlock ledger. Guarantees that
   once an achievement or milestone is earned, it is permanently preserved and
   cannot be revoked if prompts in the Vault are deleted or modified.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_daily_activities table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_activities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            activity_date DATE NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            highest_score DOUBLE PRECISION NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_user_daily_activities_user_date UNIQUE (user_id, activity_date)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_daily_activities_user_date
        ON user_daily_activities (user_id, activity_date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_daily_activities_date
        ON user_daily_activities (activity_date);
    """)

    # 2. user_unlocked_badges table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_unlocked_badges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            badge_id VARCHAR(100) NOT NULL,
            unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            progress_snapshot VARCHAR(255) NULL,
            CONSTRAINT uq_user_unlocked_badges_user_badge UNIQUE (user_id, badge_id)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_unlocked_badges_user
        ON user_unlocked_badges (user_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_unlocked_badges CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_daily_activities CASCADE;")
