from fastapi import HTTPException
from app.services.exceptions import (
    PromptNotFoundError,
    TemplateNotFoundError,
    VersionNotFoundError,
    NoTemplatesFoundError,
    PromptValidationException,
    InvalidRoleError,
    InvalidModeError,
    PromptRestoreException,
    VersionDeleteException,
    EmbeddingGenerationException,
    DatabaseTransactionException,
    LLMTimeoutException,
    LLMResponseException,
    PromptEnhancementException,
    TemplateRenderException,
    PromptAnalysisException,
    PromptComparisonException,
    SimilarityBelowThresholdError,
    NoTemplateMatchError,
)


def map_service_error(exc: Exception) -> HTTPException:
    # 400 Bad Request — Template Similarity Below Threshold / No Match
    if isinstance(exc, (SimilarityBelowThresholdError, NoTemplateMatchError)):
        return HTTPException(
            status_code=400,
            detail="Try selecting a specific role or mode, or rephrasing your prompt.",
        )

    # 404 Not Found Errors
    if isinstance(exc, (PromptNotFoundError, TemplateNotFoundError, VersionNotFoundError, NoTemplatesFoundError)):
        return HTTPException(status_code=404, detail="Requested resource or matching template was not found.")

    # 422 Unprocessable Entity / Validation Errors
    if isinstance(exc, (PromptValidationException, InvalidRoleError, InvalidModeError, TemplateRenderException)):
        return HTTPException(status_code=422, detail=str(exc))

    # 409 Conflict Errors
    if isinstance(exc, (PromptRestoreException, VersionDeleteException)):
        return HTTPException(status_code=409, detail=str(exc))

    # 500 Internal Server Errors
    if isinstance(exc, (
        EmbeddingGenerationException,
        DatabaseTransactionException,
        LLMTimeoutException,
        LLMResponseException,
        PromptEnhancementException,
        PromptAnalysisException,
        PromptComparisonException
    )):
        return HTTPException(status_code=500, detail="An internal server error occurred while processing your prompt.")

    # Fallback to 400 Bad Request
    return HTTPException(status_code=400, detail="An error occurred while processing your request. Please try again.")
