from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.addons.descriptors import _notification_event_patterns
from app.schemas.config import NotificationChannelConfig
from app.schemas.domain.event import Event, EventActor, EventLevel, EventType
from app.schemas.domain.event_catalog import is_manual_notification_suppressed
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.application.workflows.notifications.service import NotificationApplicationService


def _media() -> MediaIdentity:
    return MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), season_number=1, title="Test Show", year=2026)


def test_default_notification_channel_patterns_target_business_results():
    channel = NotificationChannelConfig(id="channel-1", type="fake", name="Fake")

    assert "download.completed" not in channel.event_patterns
    assert "media.import.*" in channel.event_patterns
    assert "subscription.ended.*" in channel.event_patterns
    assert "*" not in channel.event_patterns
    assert "subscription.*" not in channel.event_patterns


def test_notification_addon_subscribes_broadly_for_custom_channel_rules():
    patterns = _notification_event_patterns()

    assert patterns == ["*"]


@pytest.mark.parametrize("patterns", [["*"], ["addon.*"], ["addon.run.completed"]])
@pytest.mark.asyncio
async def test_addon_completion_does_not_create_notification_even_with_matching_rules(monkeypatch, patterns):
    channel = NotificationChannelConfig(id="channel-1", type="fake", event_patterns=patterns)
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.settings_service",
        SimpleNamespace(get_addons_config=lambda: SimpleNamespace(notifications=SimpleNamespace(channels=[channel]))),
    )

    def unexpected_action(**kwargs):
        pytest.fail("Internal completion must not create a notification action")

    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.action_service",
        SimpleNamespace(create_action=unexpected_action),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.notification_channel_service",
        SimpleNamespace(supports=lambda _: True, get_channel=lambda _: SimpleNamespace(is_configured=lambda _: True)),
    )

    await NotificationApplicationService().handle_event(Event(type=EventType.ADDON_RUN_COMPLETED))


@pytest.mark.parametrize("event_type", [
    EventType.ADDON_RUN_FAILED,
    EventType.MEDIA_IMPORT_COMPLETED,
])
def test_business_results_and_addon_failures_remain_notifiable(monkeypatch, event_type):
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.notification_channel_service",
        SimpleNamespace(supports=lambda _: True, get_channel=lambda _: SimpleNamespace(is_configured=lambda _: True)),
    )
    channel = NotificationChannelConfig(id="channel-1", type="fake", event_patterns=["*"])

    assert NotificationApplicationService()._should_send(channel, Event(type=event_type))


@pytest.mark.parametrize("event_type", [
    EventType.MEDIA_SERVER_SYNC_COMPLETED,
    EventType.MEDIA_SERVER_SYNC_FAILED,
    EventType.DANMU_GENERATE_COMPLETED,
    EventType.DANMU_GENERATE_FAILED,
])
def test_postprocessing_results_do_not_send_separate_notifications(event_type):
    channel = NotificationChannelConfig(id="channel-1", type="fake", event_patterns=["*"])
    assert not NotificationApplicationService()._should_send(channel, Event(type=event_type))


@pytest.mark.asyncio
async def test_import_notification_is_sent_once_only_after_summary_ready(monkeypatch):
    from app.schemas.persistence.event_dispatch import EventDispatchDeferred

    event = Event(type=EventType.MEDIA_IMPORT_COMPLETED, media=_media(), meta="{}")
    channel = NotificationChannelConfig(id="channel", type="fake", event_patterns=["*"])
    send = AsyncMock()
    create = Mock(return_value=SimpleNamespace(id="notify-action"))
    summary = AsyncMock(side_effect=[EventDispatchDeferred(), event])
    module = "app.services.application.workflows.notifications.service"
    monkeypatch.setattr(f"{module}.settings_service", SimpleNamespace(
        get_addons_config=lambda: SimpleNamespace(notifications=SimpleNamespace(channels=[channel])),
    ))
    monkeypatch.setattr(f"{module}.notification_channel_service", SimpleNamespace(
        supports=lambda _: True,
        get_channel=lambda _: SimpleNamespace(is_configured=lambda _: True, send=send),
    ))
    monkeypatch.setattr(f"{module}.action_service", SimpleNamespace(
        create_action=create, mark_running=Mock(), mark_completed=Mock(),
    ))
    monkeypatch.setattr(f"{module}.import_notification_summary_service", SimpleNamespace(build_notification=summary))
    service = NotificationApplicationService()

    with pytest.raises(EventDispatchDeferred):
        await service.handle_event(event)
    create.assert_not_called()
    send.assert_not_awaited()

    await service.handle_event(event)
    await service.handle_event(Event(type=EventType.DANMU_GENERATE_COMPLETED))
    await service.handle_event(Event(type=EventType.MEDIA_SERVER_SYNC_COMPLETED))

    send.assert_awaited_once_with(channel, event)
    assert create.call_count == 1


def test_independent_postprocessing_channel_options_normalize_to_import():
    channel = NotificationChannelConfig(type="telegram", event_patterns=[
        "media_server_sync.*", "danmu.generate.failed", "media.import.completed", "indexer.site.unhealthy",
    ])
    assert channel.event_patterns == ["media.import.*", "indexer.site.unhealthy"]


def test_manual_notification_suppression_keeps_task_change_failures_notifiable():
    assert is_manual_notification_suppressed(
        Event(id="event-1", type=EventType.DOWNLOAD_FAILED, level=EventLevel.error, actor=EventActor.user)
    )
    assert not is_manual_notification_suppressed(
        Event(
            id="event-2",
            type=EventType.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED,
            level=EventLevel.error,
            actor=EventActor.user,
        )
    )
    assert not is_manual_notification_suppressed(
        Event(
            id="event-3",
            type=EventType.DOWNLOAD_TASK_DOWNLOADER_CHANGE_FAILED,
            level=EventLevel.error,
            actor=EventActor.user,
        )
    )


def test_manual_media_delete_notification_is_suppressed_without_hiding_system_deletes():
    assert is_manual_notification_suppressed(
        Event(id="event-1", type=EventType.MEDIA_DELETED, level=EventLevel.info, actor=EventActor.user)
    )
    assert not is_manual_notification_suppressed(
        Event(id="event-2", type=EventType.MEDIA_DELETED, level=EventLevel.info, actor=EventActor.system)
    )


def test_manual_danmu_result_notifications_are_suppressed():
    assert is_manual_notification_suppressed(
        Event(id="event-1", type=EventType.DANMU_GENERATE_COMPLETED, actor=EventActor.user)
    )
    assert is_manual_notification_suppressed(
        Event(id="event-2", type=EventType.DANMU_GENERATE_FAILED, actor=EventActor.user)
    )


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
