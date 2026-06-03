from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import OptionalMediaIDParam
from app.schemas.media_id import MediaID
from app.schemas.domain.event import Event, EventCenterResponse, EventLevel, EventSource, EventType
from app.services.audit.event_service import event_service

router = APIRouter()


class EventListResponse(BaseModel):
    total: int
    items: list[Event]


class EventFilterOptionsResponse(BaseModel):
    levels: list[str]
    types: list[str]
    sources: list[str]


class EventAcknowledgeResponse(BaseModel):
    ok: bool
    acknowledged_count: int = 0


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


@router.get("/center", response_model=EventCenterResponse)
async def get_event_center() -> EventCenterResponse:
    return event_service.get_center()


@router.post("/center/acknowledge-all", response_model=EventAcknowledgeResponse)
async def acknowledge_event_center() -> EventAcknowledgeResponse:
    return EventAcknowledgeResponse(ok=True, acknowledged_count=event_service.acknowledge_attention_events())


@router.post("/{event_id}/acknowledge", response_model=EventAcknowledgeResponse)
async def acknowledge_event(event_id: str) -> EventAcknowledgeResponse:
    acknowledged = event_service.acknowledge_event(event_id)
    return EventAcknowledgeResponse(ok=acknowledged, acknowledged_count=1 if acknowledged else 0)


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
        types=[event_type.value for event_type in EventType],
        sources=[source.value for source in EventSource],
    )


class EventDetailResponse(BaseModel):
    data: Event | None = None


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: str) -> EventDetailResponse:
    return EventDetailResponse(data=event_service.get_event(event_id))
