from datetime import datetime
from types import SimpleNamespace

from app.schemas.domain.action import ActionKind, ActionRecord, ActionStatus
from app.schemas.domain.event import Event, EventCenterBellState, EventLevel, EventType
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
