import uuid
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, JSON, CheckConstraint, text, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    attributes = Column(JSON, nullable=False)
    injection_template = Column(Text, nullable=True)
    thumbnail_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=False, server_default=text("false"), nullable=False)
    use_count = Column(Integer, default=0, server_default=text("0"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('character', 'cinematic', 'art_style', 'environment', 'brand_voice')",
            name="valid_type_constraint"
        ),
    )
