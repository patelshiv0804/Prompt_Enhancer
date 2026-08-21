from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_current_user, get_session
from app.api.v1.exceptions import map_service_error
from app.core.security import get_current_user_id
from app.repositories.profile import ProfileRepository
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileSummary, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])

profile_service = ProfileService(ProfileRepository())


def _ensure_self(profile_id: str, user_id: UUID) -> None:
    """Reject access to a profile that does not belong to the caller (VULN-004)."""
    try:
        requested = UUID(str(profile_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="Profile not found")
    if requested != user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this profile")



@router.get(
    "/",
    response_model=PaginatedResponse[ProfileSummary],
    summary="List User Profiles",
    description="Retrieves a paginated list of registered user profiles. Optional query filter `is_active` can narrow results.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while fetching profiles."},
    },
)
async def list_profiles(
    user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: Optional[bool] = Query(default=None),
) -> PaginatedResponse[ProfileSummary]:
    # Scope to the authenticated caller's own profile only (VULN-004).
    try:
        profile = await profile_service.get_profile(session, str(user_id))
        data = [ProfileSummary(**profile.model_dump())]
    except Exception:
        data = []
    return PaginatedResponse(
        message="Profile list retrieved.",
        data=data,
        page=1,
        page_size=limit,
        total=len(data),
    )



@router.get(
    "/{profile_id}",
    response_model=APIResponse[ProfileRead],
    summary="Get User Profile Details",
    description="Retrieves full profile details for a specific user using their UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "The user profile with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the profile details."},
    },
)
async def get_profile(
    profile_id: str,
    user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
) -> APIResponse[ProfileRead]:
    _ensure_self(profile_id, user_id)
    try:
        profile = await profile_service.get_profile(session, profile_id)
        return APIResponse(message="Profile retrieved.", data=ProfileRead(**profile.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.put(
    "/{profile_id}",
    response_model=APIResponse[ProfileRead],
    summary="Update User Profile",
    description="Updates the email, full name, avatar, or active status on an existing user profile.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on the updated fields."},
        404: {"model": ErrorResponse, "description": "The user profile with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while updating the profile."},
    },
)
async def update_profile(
    profile_id: str,
    payload: ProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
) -> APIResponse[ProfileRead]:
    _ensure_self(profile_id, user_id)
    try:
        profile = await profile_service.update_profile(session, profile_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="Profile updated.", data=ProfileRead(**profile.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)

