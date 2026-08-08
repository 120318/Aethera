from datetime import datetime
from types import SimpleNamespace

import pytest

from app.schemas.domain.action import ActionKind, ActionRecord, ActionStatus
from app.schemas.domain.download import TaskStatus
from app.schemas.domain.event import Event, EventCenterBellState, EventCenterResponse, EventCenterSummary, EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.application.views.event_center import EventCenterViewService
from app.services.audit.action_service import ActionService
from app.services.audit.event_service import EventService


class _FakeEventRepository:
    def __init__(self) -> None:
        self.events = [
            Event(id="event-error", type=EventType.MEDIA_IMPORT_FAILED, level=EventLevel.error, ts=datetime(2026, 1, 2)),
            Event(id="event-warning", type=EventType.LIBRARY_FILE_MISSING, level=EventLevel.warning, ts=datetime(2026, 1, 1)),
            Event(id="event-info", type=EventType.MEDIA_IMPORT_COMPLETED, level=EventLevel.info, ts=datetime(2026, 1, 3)),
        ]
        self.acknowledged_ids = set()

    def list_filtered_page(self, *, limit, offset, levels=None, acknowledged=None, **_kwargs):
        events = [event for event in self.events if not levels or event.level in levels]
        if acknowledged is not None:
            events = [event for event in events if (event.id in self.acknowledged_ids) is acknowledged]
        return len(events), events[offset: offset + limit]

    def acknowledge_event(self, event_id: str) -> bool:
        if not any(event.id == event_id for event in self.events):
            return False
        self.acknowledged_ids.add(event_id)
        return True

    def acknowledge_attention_events(self) -> int:
        attention_events = [event for event in self.events if event.level in {EventLevel.warning, EventLevel.error}]
        unacknowledged_events = [event for event in attention_events if event.id not in self.acknowledged_ids]
        self.acknowledged_ids.update(event.id for event in unacknowledged_events)
        return len(unacknowledged_events)


def test_event_center_uses_warning_error_events_and_running_actions(monkeypatch):
    service = EventService()
    service.repo = _FakeEventRepository()
    captured = {}

    def list_actions(**kwargs):
        captured.update(kwargs)
        return (
            1,
            [ActionRecord(id="action-1", kind=ActionKind.command, action_name="task.transfer", status=ActionStatus.running)],
        )

    monkeypatch.setattr(
        "app.services.audit.event_service.action_service",
        SimpleNamespace(list_actions=list_actions),
    )

    center = service.get_center()

    assert captured["excluded_action_names"] == ("notification.send",)
    assert center.summary.bell_state == EventCenterBellState.error
    assert center.summary.error_event_count == 1
    assert center.summary.warning_event_count == 1
    assert center.summary.active_action_count == 1
    assert [event.id for event in center.events] == ["event-error", "event-warning"]


def test_action_service_forwards_excluded_action_names():
    captured = {}
    service = ActionService()
    service.repo = SimpleNamespace(
        list_filtered_page=lambda **kwargs: (captured.update(kwargs) or (0, [])),
    )

    total, actions = service.list_actions(excluded_action_names=("notification.send",))

    assert total == 0
    assert actions == []
    assert captured["excluded_action_names"] == ("notification.send",)


def test_event_center_hides_acknowledged_warning_error_events(monkeypatch):
    service = EventService()
    service.repo = _FakeEventRepository()
    monkeypatch.setattr(
        "app.services.audit.event_service.action_service",
        SimpleNamespace(list_actions=lambda **_kwargs: (0, [])),
    )

    assert service.acknowledge_event("event-error") is True
    center = service.get_center()

    assert center.summary.bell_state == EventCenterBellState.warning
    assert center.summary.error_event_count == 0
    assert center.summary.warning_event_count == 1
    assert [event.id for event in center.events] == ["event-warning"]


def test_event_center_acknowledges_all_attention_events(monkeypatch):
    service = EventService()
    service.repo = _FakeEventRepository()
    monkeypatch.setattr(
        "app.services.audit.event_service.action_service",
        SimpleNamespace(list_actions=lambda **_kwargs: (0, [])),
    )

    assert service.acknowledge_attention_events() == 2
    center = service.get_center()

    assert center.summary.bell_state == EventCenterBellState.idle
    assert center.summary.error_event_count == 0
    assert center.summary.warning_event_count == 0
    assert center.events == []


@pytest.mark.asyncio
async def test_event_center_includes_active_downloads_and_sets_running_state(monkeypatch):
    service = EventCenterViewService()
    media = MediaIdentity(
        media_id=MediaID.parse("tmdb:tv:2"),
        season_number=1,
        title="Show",
        year=2026,
    )
    task = SimpleNamespace(
        id="task-1",
        status=TaskStatus.DOWNLOADING,
        progress=0.42,
        context=SimpleNamespace(search_result=None, resource_title="Show.S01E01", media=media),
        metadata=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )
    monkeypatch.setattr(
        "app.services.application.views.event_center.event_service",
        SimpleNamespace(get_center=lambda: EventCenterResponse(summary=EventCenterSummary())),
    )
    calls = {}

    async def get_tasks(**kwargs):
        calls["list"] = kwargs
        return [task]

    async def count_tasks(**kwargs):
        calls["count"] = kwargs
        return 1

    monkeypatch.setattr(
        "app.services.application.views.event_center.download_service",
        SimpleNamespace(get_tasks=get_tasks, count_tasks=count_tasks),
    )

    center = await service.get_center()

    assert center.summary.active_download_count == 1
    assert center.summary.bell_state == EventCenterBellState.running
    assert center.active_downloads[0].title == "Show.S01E01"
    assert center.active_downloads[0].media == media
    assert calls["list"]["limit"] == 50
    assert calls["list"]["status"] == [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED]
    assert calls["count"]["status"] == [TaskStatus.PENDING, TaskStatus.DOWNLOADING]


@pytest.mark.asyncio
async def test_event_center_lists_paused_download_without_running_signal(monkeypatch):
    service = EventCenterViewService()
    task = SimpleNamespace(
        id="task-paused",
        status=TaskStatus.PAUSED,
        progress=0.42,
        context=SimpleNamespace(search_result=None, resource_title="Paused release", media=None),
        metadata=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )
    monkeypatch.setattr(
        "app.services.application.views.event_center.event_service",
        SimpleNamespace(get_center=lambda: EventCenterResponse(summary=EventCenterSummary())),
    )
    monkeypatch.setattr(
        "app.services.application.views.event_center.download_service",
        SimpleNamespace(
            get_tasks=lambda **_kwargs: _async_value([task]),
            count_tasks=lambda **_kwargs: _async_value(0),
        ),
    )

    center = await service.get_center()

    assert center.summary.active_download_count == 0
    assert center.summary.bell_state == EventCenterBellState.idle
    assert [item.id for item in center.active_downloads] == ["task-paused"]


async def _async_value(value):
    return value
