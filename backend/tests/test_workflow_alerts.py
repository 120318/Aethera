from types import SimpleNamespace

import pytest

from app.addons.descriptors import _notification_event_patterns
from app.schemas.config import NotificationChannelConfig
from app.schemas.domain.event import Event, EventActor, EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.application.workflows.notifications.service import NotificationApplicationService


def _media() -> MediaIdentity:
    return MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), season_number=1, title="Test Show", year=2026)


def test_default_notification_channel_patterns_target_business_results():
    channel = NotificationChannelConfig(id="channel-1", type="fake", name="Fake")

    assert "download.completed" not in channel.event_patterns
    assert "media.import.completed" in channel.event_patterns
    assert "subscription.ended.*" in channel.event_patterns
    assert "*" not in channel.event_patterns
    assert "subscription.*" not in channel.event_patterns


def test_notification_addon_does_not_subscribe_to_all_events():
    patterns = _notification_event_patterns()

    assert "*" not in patterns
    assert "notification.*" not in patterns
    assert "media.import.completed" in patterns


@pytest.mark.asyncio
async def test_notification_send_failure_marks_action_without_emitting_event(monkeypatch):
    captured = {}
    channel = NotificationChannelConfig(id="channel-1", type="fake", name="Fake", event_patterns=["media.*"])

    class FakeNotificationChannel:
        def is_configured(self, config):
            return True

        async def send(self, config, event):
            raise RuntimeError("network failed")

    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.settings_service",
        SimpleNamespace(get_addons_config=lambda: SimpleNamespace(notifications=SimpleNamespace(channels=[channel]))),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.notification_channel_service",
        SimpleNamespace(supports=lambda channel_type: True, get_channel=lambda channel_type: FakeNotificationChannel()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.action_service",
        SimpleNamespace(
            create_action=lambda **kwargs: SimpleNamespace(id="action-1"),
            mark_running=lambda *args, **kwargs: None,
            mark_failed=lambda action_id, **kwargs: captured.setdefault("failed", (action_id, kwargs.get("error"))),
            mark_completed=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.event_service",
        SimpleNamespace(emit=lambda event, meta=None: captured.setdefault("event", event)),
        raising=False,
    )

    await NotificationApplicationService().handle_event(
        Event(
            id="event-1",
            type=EventType.MEDIA_IMPORT_FAILED,
            level=EventLevel.error,
            media=_media(),
            task_id="task-1",
        )
    )

    assert captured["failed"] == ("action-1", "network failed")
    assert "event" not in captured


@pytest.mark.asyncio
async def test_notification_send_success_marks_action_without_emitting_event(monkeypatch):
    captured = {}
    channel = NotificationChannelConfig(id="channel-1", type="fake", name="Fake", event_patterns=["media.*"])

    class FakeNotificationChannel:
        def is_configured(self, config):
            return True

        async def send(self, config, event):
            captured["sent"] = (config.id, event.id)

    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.settings_service",
        SimpleNamespace(get_addons_config=lambda: SimpleNamespace(notifications=SimpleNamespace(channels=[channel]))),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.notification_channel_service",
        SimpleNamespace(supports=lambda channel_type: True, get_channel=lambda channel_type: FakeNotificationChannel()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.action_service",
        SimpleNamespace(
            create_action=lambda **kwargs: SimpleNamespace(id="action-1"),
            mark_running=lambda *args, **kwargs: None,
            mark_failed=lambda *args, **kwargs: None,
            mark_completed=lambda *args, **kwargs: captured.setdefault("completed", True),
        ),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.event_service",
        SimpleNamespace(emit=lambda event, meta=None: captured.setdefault("event", event)),
        raising=False,
    )
    await NotificationApplicationService().handle_event(
        Event(
            id="event-1",
            type=EventType.MEDIA_IMPORT_COMPLETED,
            level=EventLevel.info,
            media=_media(),
            task_id="task-1",
        )
    )

    assert captured["sent"] == ("channel-1", "event-1")
    assert captured["completed"] is True
    assert "event" not in captured


@pytest.mark.asyncio
async def test_manual_download_result_event_is_not_sent(monkeypatch):
    captured = {}
    channel = NotificationChannelConfig(id="channel-1", type="fake", name="Fake", event_patterns=["media.import.completed"])

    class FakeNotificationChannel:
        def is_configured(self, config):
            return True

        async def send(self, config, event):
            captured["sent"] = (config.id, event.id)

    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.settings_service",
        SimpleNamespace(get_addons_config=lambda: SimpleNamespace(notifications=SimpleNamespace(channels=[channel]))),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.notification_channel_service",
        SimpleNamespace(supports=lambda channel_type: True, get_channel=lambda channel_type: FakeNotificationChannel()),
    )

    await NotificationApplicationService().handle_event(
        Event(
            id="event-1",
            type=EventType.MEDIA_IMPORT_COMPLETED,
            level=EventLevel.info,
            actor=EventActor.user,
            media=_media(),
            task_id="task-1",
        )
    )

    assert "sent" not in captured
