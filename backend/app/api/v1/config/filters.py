from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.common_responses import OperationResponse
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.services.config.settings_service import settings_service

router = APIRouter()


class FilterListResponse(BaseModel):
    items: list[FilterConfig]


class FilterResponse(BaseModel):
    filter: FilterConfig

class CreateFilterRequest(BaseModel):
    name: str
    active_default: bool = False
    quality_profile_id: str | None = None
    filters: SubscriptionFilters

class UpdateFilterRequest(BaseModel):
    name: str | None = None
    active_default: bool | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None

@router.get("/config/filters", response_model=FilterListResponse)
async def list_filters() -> FilterListResponse:
    """Internal helper."""
    return FilterListResponse(items=settings_service.list_filter_presets())

@router.post("/config/filters", response_model=FilterResponse)
async def create_filter(request: CreateFilterRequest) -> FilterResponse:
    """Internal helper."""
    filter_config = settings_service.create_filter(
        name=request.name,
        filters=request.filters,
        quality_profile_id=request.quality_profile_id,
        active_default=request.active_default,
    )
    return FilterResponse(filter=filter_config)

@router.put("/config/filters/{filter_id}", response_model=FilterResponse)
async def update_filter(filter_id: str, request: UpdateFilterRequest) -> FilterResponse:
    """Internal helper."""
    filter_config = settings_service.update_filter(
        filter_id=filter_id,
        name=request.name,
        filters=request.filters,
        quality_profile_id=request.quality_profile_id,
        active_default=request.active_default,
    )
    if not filter_config:
        raise ResourceNotFoundException("backendErrors.config.filterNotFound")
    return FilterResponse(filter=filter_config)

@router.delete("/config/filters/{filter_id}", response_model=OperationResponse)
async def delete_filter(filter_id: str) -> OperationResponse:
    """Internal helper."""
    success = settings_service.delete_filter(filter_id)
    if not success:
        raise ResourceNotFoundException("backendErrors.config.filterNotFound")
    return OperationResponse(ok=True, message_key="operationMessages.config.filterDeleted")
