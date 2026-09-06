"""
Auth module — Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ──────────────────────────────────────

class UserRegister(BaseModel):
    """Registration request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Google authentication request body."""
    id_token: str = Field(..., min_length=1)


class OTPRequest(BaseModel):
    """Request OTP for account restore."""
    email: EmailStr


class OTPVerify(BaseModel):
    """Verify OTP for account restore."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    """Request OTP for password reset."""
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    """Verify OTP submitted by the user for password reset."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyResetOTPResponse(BaseModel):
    """Short-lived reset token returned after OTP is verified."""
    reset_token: str


class ResetPasswordRequest(BaseModel):
    """Set a new password using the reset token issued after OTP verification."""
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Token refresh request body (optional fallback if not using httpOnly cookie)."""
    refresh_token: Optional[str] = None


# ── Response Schemas ─────────────────────────────────────

class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: UUID


class MessageResponse(BaseModel):
    """Generic message response."""
    success: bool = True
    message: str


class UserResponse(BaseModel):
    """Public user data returned after registration."""
    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
