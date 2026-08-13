from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.api.v1.exceptions import map_service_error
from app.repositories.profile import ProfileRepository
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileSummary, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])

profile_service = ProfileService(ProfileRepository())


@router.get(
    "/",
    response_model=PaginatedResponse[ProfileSummary],
    summary="List User Profiles",
    description="Retrieves a paginated list of registered user profiles. Requires authentication.",
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while fetching profiles."},
    },
)
async def list_profiles(
    current_user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: Optional[bool] = Query(default=None),
) -> PaginatedResponse[ProfileSummary]:
    profiles = await profile_service.list_profiles(session, limit=limit, offset=offset, is_active=is_active)
    return PaginatedResponse(
        message="Profile list retrieved.",
        data=[ProfileSummary(**profile.model_dump()) for profile in profiles],
        page=(offset // limit) + 1,
        page_size=limit,
        total=len(profiles),
    )


@router.get(
    "/{profile_id}",
    response_model=APIResponse[ProfileRead],
    summary="Get User Profile Details",
    description="Retrieves full profile details for a specific user using their UUID. Users can only view their own profile.",
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Forbidden."},
        404: {"model": ErrorResponse, "description": "The user profile with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the profile details."},
    },
)
async def get_profile(
    profile_id: str,
    current_user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
) -> APIResponse[ProfileRead]:
    if str(current_user_id) != profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only view your own profile.",
        )
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
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Forbidden."},
        404: {"model": ErrorResponse, "description": "The user profile with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while updating the profile."},
    },
)
async def update_profile(
    profile_id: str,
    payload: ProfileUpdate,
    current_user_id: UUID = Depends(get_current_user_id),
    session=Depends(get_session),
) -> APIResponse[ProfileRead]:
    if str(current_user_id) != profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only update your own profile.",
        )
    try:
        profile = await profile_service.update_profile(session, profile_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="Profile updated.", data=ProfileRead(**profile.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)
