from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_current_user, get_session
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
    description="Retrieves a paginated list of registered user profiles. Optional query filter `is_active` can narrow results.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while fetching profiles."},
    },
)
async def list_profiles(
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
    description="Retrieves full profile details for a specific user using their UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "The user profile with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the profile details."},
    },
)
async def get_profile(profile_id: str, session=Depends(get_session)) -> APIResponse[ProfileRead]:
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
    session=Depends(get_session),
) -> APIResponse[ProfileRead]:
    try:
        profile = await profile_service.update_profile(session, profile_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="Profile updated.", data=ProfileRead(**profile.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)

