"""
Auth module — FastAPI router for authentication endpoints.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session
from app.schemas.auth import (
    GoogleAuthRequest,
    MessageResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
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

    # 1. Create auth user
    user = await auth_service.register(email=body.email, password=body.password)

    # 2. Create profile + default settings
    profile = await profile_service.create_profile(
        user_id=user.id,
        email=body.email,
        display_name=body.display_name,
    )
    await db.commit()
    return profile


from fastapi.security import OAuth2PasswordRequestForm

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session)
):
    """Authenticate with email/password and receive a JWT access token."""
    service = AuthService(db)
    # OAuth2PasswordRequestForm uses 'username', but we treat it as email
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
