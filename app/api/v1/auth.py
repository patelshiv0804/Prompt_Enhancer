"""
Auth module — FastAPI router for authentication endpoints.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session
from app.core.config import get_settings
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
from app.middleware.rate_limit import sensitive_rate_limiter
from app.services.auth_service import AuthService
from app.services.user_service import ProfileService
from app.schemas.user import ProfileResponse

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookie(response: Response, access_token: str) -> None:
    """Store the JWT access token in an httpOnly cookie (VULN-017)."""
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


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
    dependencies=[Depends(sensitive_rate_limiter)],
)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session),
):
    """Authenticate with email/password and receive a JWT access token.

    The token is also set as an httpOnly cookie so browser clients never
    need to store it in JavaScript-accessible storage.
    """
    service = AuthService(db)
    token = await service.login(email=form_data.username, password=form_data.password)
    _set_auth_cookie(response, token.access_token)
    return token


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Login or register with Google",
)
async def google_auth(
    response: Response,
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_session),
):
    """Exchange a verified Google ID token for the app's JWT."""
    service = AuthService(db)
    token = await service.authenticate_with_google(body.id_token)
    await db.commit()
    _set_auth_cookie(response, token.access_token)
    return token


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and clear the auth cookie",
)
async def logout(response: Response):
    """Clear the httpOnly auth cookie."""
    response.delete_cookie(
        key=settings.access_cookie_name,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
    )
    return MessageResponse(message="Logged out successfully.")


# ── Forgot Password / OTP Reset ──────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset OTP",
    dependencies=[Depends(sensitive_rate_limiter)],
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
    dependencies=[Depends(sensitive_rate_limiter)],
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
    dependencies=[Depends(sensitive_rate_limiter)],
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
