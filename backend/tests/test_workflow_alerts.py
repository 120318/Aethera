from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.config import NotificationChannelConfig
from app.schemas.domain.alert import AlertCategory, AlertTargetType
from app.schemas.domain.event import Event, EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.application.workflows.notifications.service import NotificationApplicationService
from app.services.domain.alerts import workflow_alerts


def _media() -> MediaIdentity:
    return MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), season_number=1, title="Test Show", year=2026)


def test_raise_danmu_alert_uses_video_path_fingerprint_and_reason_key(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_alerts,
        "alert_service",
        SimpleNamespace(raise_alert=lambda request: captured.setdefault("request", request)),
    )

    workflow_alerts.raise_danmu_alert(
        media=_media(),
        video_path=Path("/data/library/Test Show - S01E01.mkv"),
        action_id="action-1",
        task_id="task-1",
        provider="youku",
        error_key="runtimeReasons.danmuNotFound",
    )

    request = captured["request"]
    assert request.fingerprint == "danmu.generate:/data/library/Test Show - S01E01.mkv"
    assert request.category == AlertCategory.danmu_generate
    assert request.target_type == AlertTargetType.danmu_sidecar
    assert request.message_key == "alertMessages.danmuGenerateFailed"
    assert request.message_params["target"] == "Test Show - S01E01.mkv"
    assert request.message_params["provider"] == "youku"
    assert request.message_params["reason_key"] == "runtimeReasons.danmuNotFound"


def test_media_server_sync_alert_resolves_same_file_fingerprint(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_alerts,
        "alert_service",
        SimpleNamespace(
            raise_alert=lambda request: captured.setdefault("raise", request),
            resolve_alert=lambda request: captured.setdefault("resolve", request),
        ),
    )

    workflow_alerts.raise_media_server_sync_alert(
        media=_media(),
        file_path="/data/library/Test Show - S01E01.mkv",
        media_server_id="server-1",
        task_id="task-1",
        error="write failed",
    )
    workflow_alerts.resolve_media_server_sync_alert(
        media=_media(),
        file_path="/data/library/Test Show - S01E01.mkv",
        media_server_id="server-1",
    )

    assert captured["raise"].fingerprint == "media_server_sync:server-1:/data/library/Test Show - S01E01.mkv"
    assert captured["raise"].category == AlertCategory.media_server_sync
    assert captured["raise"].target_type == AlertTargetType.library_file
    assert captured["raise"].message_params["reason"] == "write failed"
    assert captured["resolve"].fingerprint == captured["raise"].fingerprint


def test_notification_alert_uses_channel_fingerprint(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_alerts,
        "alert_service",
        SimpleNamespace(raise_alert=lambda request: captured.setdefault("request", request)),
    )

    workflow_alerts.raise_notification_alert(
        channel_id="channel-1",
        channel_name="Telegram",
        channel_type="telegram",
        event_type="media.import.failed",
        event_id="event-1",
        media=_media(),
        media_id=None,
        task_id="task-1",
        action_id="action-1",
        error="network failed",
    )

    request = captured["request"]
    assert request.fingerprint == "notification.send:channel-1"
    assert request.category == AlertCategory.notification_send
    assert request.target_type == AlertTargetType.notification_channel
    assert request.message_key == "alertMessages.notificationSendFailed"
    assert request.message_params["channel"] == "Telegram"
    assert request.message_params["event_type"] == "media.import.failed"


@pytest.mark.asyncio
async def test_notification_send_failure_raises_alert_with_event_type_value(monkeypatch):
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
            mark_failed=lambda *args, **kwargs: None,
            mark_completed=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.notifications.service.raise_notification_alert",
        lambda **kwargs: captured.setdefault("alert", kwargs),
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

    assert captured["alert"]["event_type"] == "media.import.failed"
    assert captured["alert"]["channel_id"] == "channel-1"
    assert captured["alert"]["action_id"] == "action-1"
