from fastapi import HTTPException

from app.services.exceptions import (
    ActiveVersionDeletionError,
    EntityNotFoundError,
    NoTemplateMatchError,
    PromptNotFoundError,
    TemplateNotFoundError,
    VersionNotFoundError,
)


def map_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (PromptNotFoundError, EntityNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, TemplateNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, VersionNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, ActiveVersionDeletionError):
        return HTTPException(status_code=409, detail=str(exc))

    if isinstance(exc, NoTemplateMatchError):
        return HTTPException(status_code=404, detail=str(exc))

    return HTTPException(status_code=400, detail=str(exc))
