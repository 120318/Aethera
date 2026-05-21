from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.config import BrowseSource
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.domain.discover import DiscoverList, DiscoverListMeta
from app.services.application.workflows.discover import discover_service

router = APIRouter()
class DiscoverListsResponse(BaseModel):
    data: list[DiscoverList]


class DiscoverListsMetaResponse(BaseModel):
    data: list[DiscoverListMeta]


@router.get("/lists/options", response_model=DiscoverListsMetaResponse)
async def get_lists_options(source: BrowseSource | None = Query(None)):
    return DiscoverListsMetaResponse(data=discover_service.list_options(source))


@router.get("/lists", response_model=DiscoverListsResponse)
async def get_lists(
    keys: str | None = Query(None, description="Comma separated list keys"),
    count: int = Query(30, ge=1, le=50),
) -> DiscoverListsResponse:
    try:
        return DiscoverListsResponse(data=await discover_service.get_lists(keys, count))
    except ValueError as exc:
        raise InvalidRequestException("backendErrors.discoverListInvalid", params={"reason": str(exc)}) from exc
