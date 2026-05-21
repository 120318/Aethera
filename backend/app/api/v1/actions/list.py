from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import OptionalMediaIDParam
from app.schemas.domain.action import (
    ActionKind,
    ActionRecord,
    ActionSource,
    ActionStatus,
    ActionTargetType,
    ActionTrigger,
)
from app.schemas.media_id import MediaID
from app.schemas.domain.event import Event
from app.services.audit.action_log_service import action_log_service
from app.services.audit.action_service import action_service
from app.services.audit.event_service import event_service

router = APIRouter()


class ActionListResponse(BaseModel):
    total: int
    items: list[ActionRecord]


class ActionFilterOptionsResponse(BaseModel):
    kinds: list[str]
    statuses: list[str]
    action_names: list[str]
    triggers: list[str]
    sources: list[str]


class ActionDetailResponse(BaseModel):
    data: ActionRecord | None = None
    events: list[Event] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


@router.get("/", response_model=ActionListResponse)
async def list_actions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    task_id: str | None = None,
    subscription_id: str | None = None,
    target_type: ActionTargetType | None = None,
    target_id: str | None = None,
    kind: list[ActionKind] | None = Query(None),
    status: list[ActionStatus] | None = Query(None),
    action_name: list[str] | None = Query(None),
    trigger: list[ActionTrigger] | None = Query(None),
    source: list[ActionSource] | None = Query(None),
    keyword: str | None = None,
    correlation_id: str | None = None,
) -> ActionListResponse:
    total, items = action_service.list_actions(
        limit=limit,
        offset=offset,
        media_id=media_id,
        task_id=task_id,
        subscription_id=subscription_id,
        target_type=target_type,
        target_id=target_id,
        kinds=kind,
        statuses=status,
        action_names=action_name,
        triggers=trigger,
        sources=source,
        keyword=keyword,
        correlation_id=correlation_id,
    )
    return ActionListResponse(total=total, items=items)


@router.get("/active", response_model=ActionListResponse)
async def list_active_actions(
    limit: int = Query(default=50, ge=1, le=200),
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    task_id: str | None = None,
    subscription_id: str | None = None,
    target_type: ActionTargetType | None = None,
    target_id: str | None = None,
    kind: list[ActionKind] | None = Query(None),
    action_name: list[str] | None = Query(None),
    trigger: list[ActionTrigger] | None = Query(None),
    source: list[ActionSource] | None = Query(None),
    keyword: str | None = None,
    correlation_id: str | None = None,
) -> ActionListResponse:
    total, items = action_service.list_actions(
        limit=limit,
        offset=0,
        media_id=media_id,
        task_id=task_id,
        subscription_id=subscription_id,
        target_type=target_type,
        target_id=target_id,
        kinds=kind,
        statuses=[ActionStatus.queued, ActionStatus.running],
        action_names=action_name,
        triggers=trigger,
        sources=source,
        keyword=keyword,
        correlation_id=correlation_id,
    )
    return ActionListResponse(total=total, items=items)


@router.get("/filter-options", response_model=ActionFilterOptionsResponse)
async def get_action_filter_options(
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    task_id: str | None = None,
    subscription_id: str | None = None,
    target_type: ActionTargetType | None = None,
    target_id: str | None = None,
    keyword: str | None = None,
    correlation_id: str | None = None,
) -> ActionFilterOptionsResponse:
    return ActionFilterOptionsResponse(
        **action_service.list_filter_options(
            media_id=media_id,
            task_id=task_id,
            subscription_id=subscription_id,
            target_type=target_type,
            target_id=target_id,
            keyword=keyword,
            correlation_id=correlation_id,
        )
    )


@router.get("/{action_id}", response_model=ActionDetailResponse)
async def get_action(action_id: str) -> ActionDetailResponse:
    action = action_service.get_action(action_id)
    if not action:
        return ActionDetailResponse()
    _, events = event_service.list_events(limit=200, action_id=action_id)
    logs = action_log_service.list_action_logs(action_id, limit=200)
    return ActionDetailResponse(data=action, events=events, logs=logs)
