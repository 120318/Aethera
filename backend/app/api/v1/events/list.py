from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import OptionalMediaIDParam
from app.schemas.constants.event_types import EventTypes
from app.schemas.media_id import MediaID
from app.schemas.domain.event import Event, EventLevel, EventSource, EventType
from app.services.audit.event_service import event_service

router = APIRouter()


class EventListResponse(BaseModel):
    total: int
    items: list[Event]


class EventFilterOptionsResponse(BaseModel):
    levels: list[str]
    types: list[str]
    sources: list[str]


@router.get("/", response_model=EventListResponse)
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    season_number: int | None = Query(default=None, gt=0),
    task_id: str | None = None,
    subscription_id: str | None = None,
    level: list[EventLevel] | None = Query(None),
    type: list[EventType] | None = Query(None),
    keyword: str | None = None,
    source: list[EventSource] | None = Query(None),
    addon_id: str | None = None,
    action_id: str | None = None,
) -> EventListResponse:
    total, items = event_service.list_events(
        limit=limit,
        offset=offset,
        media_id=media_id,
        season_number=season_number,
        task_id=task_id,
        subscription_id=subscription_id,
        levels=level,
        types=type,
        keyword=keyword,
        sources=source,
        addon_id=addon_id,
        action_id=action_id,
    )
    return EventListResponse(total=total, items=items)


@router.get("/filter-options", response_model=EventFilterOptionsResponse)
async def get_event_filter_options(
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    season_number: int | None = Query(default=None, gt=0),
    task_id: str | None = None,
    subscription_id: str | None = None,
    action_id: str | None = None,
    keyword: str | None = None,
) -> EventFilterOptionsResponse:
    _ = (media_id, season_number, task_id, subscription_id, action_id, keyword)
    return EventFilterOptionsResponse(
        levels=[level.value for level in EventLevel],
        types=[
            EventTypes.DOWNLOAD_STARTED.value,
            EventTypes.DOWNLOAD_COMPLETED.value,
            EventTypes.DOWNLOAD_FAILED.value,
            EventTypes.MEDIA_IMPORT_STARTED.value,
            EventTypes.MEDIA_IMPORT_COMPLETED.value,
            EventTypes.MEDIA_IMPORT_FAILED.value,
            EventTypes.MEDIA_SERVER_SYNC_STARTED.value,
            EventTypes.MEDIA_SERVER_SYNC_COMPLETED.value,
            EventTypes.MEDIA_SERVER_SYNC_FAILED.value,
            EventTypes.DANMU_GENERATE_STARTED.value,
            EventTypes.DANMU_GENERATE_COMPLETED.value,
            EventTypes.DANMU_GENERATE_FAILED.value,
            EventTypes.MEDIA_DELETED.value,
            EventTypes.SUBSCRIPTION_ENABLED.value,
            EventTypes.SUBSCRIPTION_DISABLED.value,
            EventTypes.FOLLOW_ENABLED.value,
            EventTypes.FOLLOW_DISABLED.value,
            EventTypes.FOLLOW_RELEASED.value,
            EventTypes.FOLLOW_DIGITAL_RELEASED.value,
            EventTypes.FOLLOW_PHYSICAL_RELEASED.value,
            EventTypes.SUBSCRIPTION_RUN_COMPLETED.value,
            EventTypes.SUBSCRIPTION_RUN_FAILED.value,
            EventTypes.PILOT_EPISODE_QUEUED.value,
        ],
        sources=[source.value for source in EventSource],
    )


class EventDetailResponse(BaseModel):
    data: Event | None = None


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: str) -> EventDetailResponse:
    return EventDetailResponse(data=event_service.get_event(event_id))
