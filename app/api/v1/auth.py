"""
Auth module — FastAPI router for authentication endpoints.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyResetOTPRequest,
    VerifyResetOTPResponse,
)
from app.services.auth_service import AuthService
from app.services.user_service import ProfileService
from app.schemas.user import ProfileResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(body: UserRegister, db: AsyncSession = Depends(get_session)):
    """
    Register a new user account.
    Creates the auth user, profile, and default settings in one transaction.
    """
    auth_service = AuthService(db)
    profile_service = ProfileService(db)

    user = await auth_service.register(email=body.email, password=body.password)
    profile = await profile_service.create_profile(
        user_id=user.id,
        email=body.email,
        display_name=body.display_name,
    )
    await db.commit()
    return profile


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session),
):
    """Authenticate with email/password and receive a JWT access token."""
    service = AuthService(db)
    return await service.login(email=form_data.username, password=form_data.password)


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Login or register with Google",
)
async def google_auth(
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_session),
):
    """Exchange a verified Google ID token for the app's JWT."""
    service = AuthService(db)
    token = await service.authenticate_with_google(body.id_token)
    await db.commit()
    return token


# ── Forgot Password / OTP Reset ──────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset OTP",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """
    Send a 6-digit OTP to the user's email address for password reset.
    Always returns 200 OK — we do not reveal whether the email exists (security best practice).
    """
    service = AuthService(db)
    background_tasks.add_task(service.request_password_reset_otp, body.email)
    return MessageResponse(
        message="If that email is registered, a reset code has been sent."
    )


@router.post(
    "/verify-reset-otp",
    response_model=VerifyResetOTPResponse,
    summary="Verify OTP and receive a password-reset token",
)
async def verify_reset_otp(
    body: VerifyResetOTPRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Validate the 6-digit OTP. On success, returns a short-lived (15 min) reset token
    that must be presented to /reset-password within that window.
    """
    service = AuthService(db)
    reset_token = await service.verify_password_reset_otp(
        email=body.email, otp=body.otp
    )
    return VerifyResetOTPResponse(reset_token=reset_token)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Set a new password using the reset token",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Consume the reset token issued after OTP verification and update the user's password.
    The token is valid for 15 minutes and is single-use by design.
    """
    service = AuthService(db)
    await service.reset_password(
        reset_token=body.reset_token,
        new_password=body.new_password,
    )
    return MessageResponse(
        message="Password has been reset successfully. You can now sign in."
    )
