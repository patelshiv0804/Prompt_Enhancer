"""
Users module — SQLAlchemy models for `profiles` and `user_settings` tables.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Profile(Base):
    """
    Profiles table — extends the auth users table with app-specific data.
    Auto-created during registration.
    """

    __tablename__ = "profiles"

    id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    email = Column(Text, nullable=False, index=True)
    display_name = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    plan = Column(Text, nullable=False, default="free")
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)

    # Relationship to settings (one-to-one)
    settings = relationship(
        "UserSettings", back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, email={self.email}, plan={self.plan})>"

    @property
    def is_deleted(self) -> bool:
        """Check if account is soft-deleted."""
        return self.deleted_at is not None


class UserSettings(Base):
    """
    User settings table — stores all preferences and UI settings.
    One row per user, separate from profile to avoid bloating.
    """

    __tablename__ = "user_settings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    theme = Column(Text, nullable=False, default="system")
    default_mode = Column(Text, nullable=False, default="general")
    default_model = Column(Text, nullable=False, default="chatgpt")
    show_diff_by_default = Column(Boolean, nullable=False, default=True)
    auto_detect_intent = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Back-reference to profile
    profile = relationship("Profile", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, theme={self.theme})>"
