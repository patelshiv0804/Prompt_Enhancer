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
