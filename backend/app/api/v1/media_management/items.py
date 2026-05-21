from typing import Literal

from fastapi import APIRouter, Query
from app.schemas.domain.media_types import MediaType
from app.schemas.runtime.media_management import MediaManagementItemsPage
from app.services.application.views.media_management import media_management_service

router = APIRouter()


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    values = [item.strip() for item in value.split(",")]
    items = [item for item in values if item]
    return items or None


@router.get("/items", response_model=MediaManagementItemsPage)
async def list_media_management_items(
    query: str | None = None,
    media_type: MediaType | None = Query(default=None),
    statuses: str | None = None,
    sort: Literal["activity", "title", "tasks", "library", "issues"] = "activity",
    direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MediaManagementItemsPage:
    return await media_management_service.list_items(
        statuses=_split_csv(statuses),
        query=query,
        media_type=media_type,
        sort=sort,
        direction=direction,
        limit=limit,
        offset=offset,
    )
