from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.common_responses import OperationResponse
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.schemas.config import Tag
from app.services.config.settings_service import settings_service

router = APIRouter()


class TagListResponse(BaseModel):
    items: list[Tag]


class TagResponse(BaseModel):
    tag: Tag


class CreateTagRequest(BaseModel):
    name: str
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    regex: str | None = None


class UpdateTagRequest(BaseModel):
    name: str | None = None
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    regex: str | None = None


@router.get("/config/tags", response_model=TagListResponse)
async def list_tags() -> TagListResponse:
    """Internal helper."""
    return TagListResponse(items=settings_service.list_tags())

@router.post("/config/tags", response_model=TagResponse)
async def create_tag(request: CreateTagRequest) -> TagResponse:
    """Internal helper."""
    tag = settings_service.create_tag(
        name=request.name,
        include_keywords=request.include_keywords,
        exclude_keywords=request.exclude_keywords,
        regex=request.regex,
    )
    return TagResponse(tag=tag)


@router.put("/config/tags/{tag_id}", response_model=TagResponse)
async def update_tag(tag_id: str, request: UpdateTagRequest) -> TagResponse:
    """Internal helper."""
    tag = settings_service.update_tag(
        tag_id=tag_id,
        name=request.name,
        include_keywords=request.include_keywords,
        exclude_keywords=request.exclude_keywords,
        regex=request.regex,
    )
    if not tag:
        raise ResourceNotFoundException("backendErrors.config.tagNotFound")
    return TagResponse(tag=tag)


@router.delete("/config/tags/{tag_id}", response_model=OperationResponse)
async def delete_tag(tag_id: str) -> OperationResponse:
    """Internal helper."""
    success = settings_service.delete_tag(tag_id)
    if not success:
        raise ResourceNotFoundException("backendErrors.config.tagNotFound")
    return OperationResponse(ok=True, message_key="operationMessages.config.tagDeleted")
