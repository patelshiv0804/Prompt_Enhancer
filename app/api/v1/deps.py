from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from jose import jwt, JWTError

from app.db.session import get_async_session
from app.core.config import get_settings
from app.db.models import User

settings = get_settings()


async def get_session(session: AsyncSession = Depends(get_async_session)) -> AsyncSession:
    return session


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> Optional[str]:
    """Retrieves the current user's email from a validated JWT.

    The token is read from the Authorization: Bearer header or, failing that,
    from the httpOnly auth cookie set at login. Returns None when no valid
    token is present. There is intentionally no header-based identity fallback.

    A valid token always wins; the dev bypass is only a last resort so that the
    two auth dependencies (this and ``get_current_user_id``) resolve to the same
    identity in every scenario.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        token = request.cookies.get(settings.access_cookie_name)

    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                from uuid import UUID
                statement = select(User).where(User.id == UUID(user_id))
                result = await session.execute(statement)
                user = result.scalar_one_or_none()
                if user:
                    return user.email
        except (JWTError, ValueError):
            pass

    if settings.enable_dev_auth_bypass:
        from uuid import UUID
        from app.db.models import Profile
        dev_uuid = UUID("899fd613-4e56-4921-b8f6-7fc1bf85fead")
        statement = select(Profile).where(Profile.id == dev_uuid)
        result = await session.execute(statement)
        profile = result.scalar_one_or_none()
        if profile:
            return profile.email

    return None


# Repositories & Databases
from app.repositories.template import TemplateRepository
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.repositories.profile import ProfileRepository

def get_template_repository() -> TemplateRepository:
    return TemplateRepository()

def get_prompt_repository() -> PromptRepository:
    return PromptRepository()

def get_prompt_version_repository() -> PromptVersionRepository:
    return PromptVersionRepository()

def get_profile_repository() -> ProfileRepository:
    return ProfileRepository()

# Provider Client & Low-level Services
from app.services.llm.factory import LLMFactory
from app.services.llm.base import BaseLLMProvider
from app.services.embedding_service import EmbeddingService
from app.services.ranking_service import RankingService
from app.services.template_renderer import TemplateRenderer
from app.services.prompt_builder import PromptBuilder

def get_llm_provider() -> BaseLLMProvider:
    return LLMFactory.get_provider()

def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

def get_ranking_service() -> RankingService:
    return RankingService()

def get_template_renderer() -> TemplateRenderer:
    return TemplateRenderer()

def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()

# Core Orchestration and Business Services
from app.services.template_retrieval_service import TemplateRetrievalService
from app.services.prompt_enhancement_service import PromptEnhancementService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.prompt_comparison_service import PromptComparisonService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_persistence_service import PromptPersistenceService
from app.services.prompt_history_service import PromptHistoryService
from app.services.prompt_service import PromptService
from app.services.prompt_regeneration_service import PromptRegenerationService
from app.services.prompt_reenhance_service import PromptReenhanceService
from app.services.intent_analysis_service import IntentAnalysisService
from app.services.role_resolution_service import RoleResolutionService
from app.services.mode_resolution_service import ModeResolutionService
from app.services.candidate_template_service import CandidateTemplateService

def get_intent_analysis_service(
    llm: BaseLLMProvider = Depends(get_llm_provider),
) -> IntentAnalysisService:
    return IntentAnalysisService(llm_provider=llm)

def get_role_resolution_service(
    emb: EmbeddingService = Depends(get_embedding_service),
) -> RoleResolutionService:
    return RoleResolutionService(embedding_service=emb)

def get_mode_resolution_service(
    emb: EmbeddingService = Depends(get_embedding_service),
) -> ModeResolutionService:
    return ModeResolutionService(embedding_service=emb)

def get_candidate_template_service(
    repo: TemplateRepository = Depends(get_template_repository),
) -> CandidateTemplateService:
    return CandidateTemplateService(repository=repo)

def get_template_retrieval_service(
    repo: TemplateRepository = Depends(get_template_repository),
    ranking: RankingService = Depends(get_ranking_service),
    emb: EmbeddingService = Depends(get_embedding_service),
    intent: IntentAnalysisService = Depends(get_intent_analysis_service),
    role_res: RoleResolutionService = Depends(get_role_resolution_service),
    mode_res: ModeResolutionService = Depends(get_mode_resolution_service),
    candidate: CandidateTemplateService = Depends(get_candidate_template_service),
) -> TemplateRetrievalService:
    return TemplateRetrievalService(
        repository=repo,
        ranking_service=ranking,
        embedding_service=emb,
        intent_service=intent,
        role_resolver=role_res,
        mode_resolver=mode_res,
        candidate_service=candidate,
    )

def get_prompt_enhancement_service(
    llm: BaseLLMProvider = Depends(get_llm_provider),
    retrieval: TemplateRetrievalService = Depends(get_template_retrieval_service),
    renderer: TemplateRenderer = Depends(get_template_renderer),
    builder: PromptBuilder = Depends(get_prompt_builder),
) -> PromptEnhancementService:
    return PromptEnhancementService(llm_provider=llm, retrieval_service=retrieval, template_renderer=renderer, prompt_builder=builder)

def get_prompt_analysis_service(
    llm: BaseLLMProvider = Depends(get_llm_provider),
) -> PromptAnalysisService:
    return PromptAnalysisService(llm_provider=llm)

def get_prompt_comparison_service(
    llm: BaseLLMProvider = Depends(get_llm_provider),
) -> PromptComparisonService:
    return PromptComparisonService(llm_provider=llm)

def get_prompt_embedding_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    version_repo: PromptVersionRepository = Depends(get_prompt_version_repository),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> PromptEmbeddingService:
    return PromptEmbeddingService(prompt_repository=prompt_repo, prompt_version_repository=version_repo, embedding_service=emb)

def get_prompt_version_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    version_repo: PromptVersionRepository = Depends(get_prompt_version_repository),
    emb_service: PromptEmbeddingService = Depends(get_prompt_embedding_service),
) -> PromptVersionService:
    return PromptVersionService(prompt_repository=prompt_repo, prompt_version_repository=version_repo, prompt_embedding_service=emb_service)

def get_prompt_persistence_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    version_service: PromptVersionService = Depends(get_prompt_version_service),
    emb_service: PromptEmbeddingService = Depends(get_prompt_embedding_service),
) -> PromptPersistenceService:
    return PromptPersistenceService(prompt_repository=prompt_repo, prompt_version_service=version_service, prompt_embedding_service=emb_service)

def get_prompt_regeneration_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    template_repo: TemplateRepository = Depends(get_template_repository),
    version_service: PromptVersionService = Depends(get_prompt_version_service),
    emb_service: PromptEmbeddingService = Depends(get_prompt_embedding_service),
    analysis: PromptAnalysisService = Depends(get_prompt_analysis_service),
    llm: BaseLLMProvider = Depends(get_llm_provider),
    enhancement: PromptEnhancementService = Depends(get_prompt_enhancement_service),
) -> PromptRegenerationService:
    return PromptRegenerationService(
        prompt_repository=prompt_repo,
        template_repository=template_repo,
        prompt_version_service=version_service,
        prompt_embedding_service=emb_service,
        analysis_service=analysis,
        llm_provider=llm,
        enhancement_service=enhancement,
    )

def get_prompt_reenhance_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    template_repo: TemplateRepository = Depends(get_template_repository),
    version_repo: PromptVersionRepository = Depends(get_prompt_version_repository),
    version_service: PromptVersionService = Depends(get_prompt_version_service),
    emb_service: PromptEmbeddingService = Depends(get_prompt_embedding_service),
    analysis: PromptAnalysisService = Depends(get_prompt_analysis_service),
    enhancement: PromptEnhancementService = Depends(get_prompt_enhancement_service),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> PromptReenhanceService:
    from app.services.tool_recommendation_service import ToolRecommendationService
    tool_rec = ToolRecommendationService(embedding_service=emb)
    return PromptReenhanceService(
        prompt_repository=prompt_repo,
        template_repository=template_repo,
        prompt_version_repository=version_repo,
        prompt_version_service=version_service,
        prompt_embedding_service=emb_service,
        analysis_service=analysis,
        tool_recommendation_service=tool_rec,
        enhancement_service=enhancement,
    )

def get_prompt_history_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    version_repo: PromptVersionRepository = Depends(get_prompt_version_repository),
) -> PromptHistoryService:
    return PromptHistoryService(prompt_repository=prompt_repo, prompt_version_repository=version_repo)

from app.services.prompt_service import PromptService
from app.services.prompt_similarity_service import PromptSimilarityService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.prompt_recommendation_service import PromptRecommendationService
from app.services.prompt_search_service import PromptSearchService

def get_prompt_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
) -> PromptService:
    return PromptService(repository=prompt_repo)

def get_prompt_similarity_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> PromptSimilarityService:
    return PromptSimilarityService(prompt_repository=prompt_repo, embedding_service=emb)

def get_duplicate_detection_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> DuplicateDetectionService:
    return DuplicateDetectionService(prompt_repository=prompt_repo, embedding_service=emb)

def get_prompt_recommendation_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> PromptRecommendationService:
    return PromptRecommendationService(prompt_repository=prompt_repo, embedding_service=emb)

def get_prompt_search_service(
    prompt_repo: PromptRepository = Depends(get_prompt_repository),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> PromptSearchService:
    return PromptSearchService(prompt_repository=prompt_repo, embedding_service=emb)

# Tool Recommendation
from app.services.tool_recommendation_service import ToolRecommendationService

def get_tool_recommendation_service(
    emb: EmbeddingService = Depends(get_embedding_service),
) -> ToolRecommendationService:
    return ToolRecommendationService(embedding_service=emb)

# Prompt Classification (enhancement depth)
from app.services.prompt_classification_service import PromptClassificationService

def get_prompt_classification_service(
    llm: BaseLLMProvider = Depends(get_llm_provider),
) -> PromptClassificationService:
    return PromptClassificationService(llm_provider=llm)
