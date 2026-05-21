from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.v1.common_responses import OperationResponse
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.quality_ranking import QualityRankingConfig
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.config.settings_service import settings_service

router = APIRouter()


class QualityProfileListResponse(BaseModel):
    items: list[QualityProfile]


class QualityProfileResponse(BaseModel):
    profile: QualityProfile


class CreateQualityProfileRequest(BaseModel):
    name: str
    active_default: bool = False
    ranking: QualityRankingConfig = Field(default_factory=QualityRankingConfig)
    min_score: int | None = None
    tag_scores: dict[str, int] | None = None


class UpdateQualityProfileRequest(BaseModel):
    name: str | None = None
    active_default: bool | None = None
    ranking: QualityRankingConfig | None = None
    min_score: int | None = None
    tag_scores: dict[str, int] | None = None


@router.get("/config/quality_profiles", response_model=QualityProfileListResponse)
async def list_quality_profiles() -> QualityProfileListResponse:
    return QualityProfileListResponse(items=settings_service.list_quality_profiles())


@router.post("/config/quality_profiles", response_model=QualityProfileResponse)
async def create_quality_profile(request: CreateQualityProfileRequest) -> QualityProfileResponse:
    profile = settings_service.create_quality_profile(
        name=request.name,
        ranking=request.ranking,
        min_score=request.min_score,
        tag_scores=request.tag_scores,
        active_default=request.active_default,
    )
    return QualityProfileResponse(profile=profile)


@router.put("/config/quality_profiles/{profile_id}", response_model=QualityProfileResponse)
async def update_quality_profile(profile_id: str, request: UpdateQualityProfileRequest) -> QualityProfileResponse:
    updates = request.model_dump(exclude_unset=True)
    profile = settings_service.update_quality_profile(profile_id, **updates)
    if not profile:
        raise ResourceNotFoundException("backendErrors.config.qualityProfileNotFound")
    return QualityProfileResponse(profile=profile)


@router.delete("/config/quality_profiles/{profile_id}", response_model=OperationResponse)
async def delete_quality_profile(profile_id: str) -> OperationResponse:
    success = settings_service.delete_quality_profile(profile_id)
    if not success:
        raise ResourceNotFoundException("backendErrors.config.qualityProfileNotFound")
    return OperationResponse(ok=True, message_key="operationMessages.config.qualityProfileDeleted")
