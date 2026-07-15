from __future__ import annotations


class ServiceError(Exception):
    pass


class TemplateSearchError(ServiceError):
    pass


class TemplateNotFoundError(ServiceError):
    pass


class PromptNotFoundError(ServiceError):
    pass


class EntityNotFoundError(ServiceError):
    pass


class VersionNotFoundError(ServiceError):
    pass


class VersionRestoreError(ServiceError):
    pass


class ActiveVersionDeletionError(ServiceError):
    pass


class EmbeddingGenerationError(ServiceError):
    pass


class PromptAnalysisError(ServiceError):
    pass


class PromptOptimizationError(ServiceError):
    pass


class PromptPersistenceError(ServiceError):
    pass


class InvalidTemplateModeError(ServiceError):
    pass


class NoTemplateMatchError(ServiceError):
    pass


class InvalidRoleError(ServiceError):
    pass


class InvalidModeError(ServiceError):
    pass


class NoTemplatesFoundError(ServiceError):
    pass


class SimilarityBelowThresholdError(ServiceError):
    pass


class DatabaseFailureError(ServiceError):
    pass


class TemplateRenderException(ServiceError):
    pass


class PromptValidationException(ServiceError):
    pass


class PromptEnhancementException(ServiceError):
    pass


class LLMTimeoutException(ServiceError):
    pass


class LLMResponseException(ServiceError):
    pass


class PromptAnalysisException(ServiceError):
    pass


class PromptComparisonException(ServiceError):
    pass


class ScoringException(ServiceError):
    pass


class AnalysisTimeoutException(ServiceError):
    pass


class PromptPersistenceException(ServiceError):
    pass


class PromptVersionException(ServiceError):
    pass


class PromptRestoreException(ServiceError):
    pass


class EmbeddingGenerationException(ServiceError):
    pass


class VersionDeleteException(ServiceError):
    pass


class DatabaseTransactionException(ServiceError):
    pass


class PromptSearchException(ServiceError):
    pass


class DuplicateDetectionException(ServiceError):
    pass


class PromptRecommendationException(ServiceError):
    pass


class SemanticSearchException(ServiceError):
    pass


class EmbeddingSearchException(ServiceError):
    pass
