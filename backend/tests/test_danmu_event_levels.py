from pathlib import Path

from app.schemas.domain.event import EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.audit import workflow_event_emitters


def _media() -> MediaIdentity:
    return MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), season_number=1, title="Test Show", year=2026)


def test_danmu_not_found_event_is_info(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_event_emitters.event_service,
        "emit_media",
        lambda event, meta=None: captured.setdefault("event", event),
    )

    workflow_event_emitters.emit_danmu_generate_event(
        EventType.DANMU_GENERATE_FAILED,
        _media(),
        Path("/data/Test Show S01E01.mkv"),
        1,
        "action-1",
        "task-1",
        error_key="runtimeReasons.danmuNotFound",
    )

    assert captured["event"].level == EventLevel.info


def test_danmu_duration_mismatch_event_is_info(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_event_emitters.event_service,
        "emit_media",
        lambda event, meta=None: captured.setdefault("event", event),
    )

    workflow_event_emitters.emit_danmu_generate_event(
        EventType.DANMU_GENERATE_FAILED,
        _media(),
        Path("/data/Test Show S01E01.mkv"),
        1,
        "action-1",
        "task-1",
        error_key="runtimeReasons.danmuDurationMismatch",
    )

    assert captured["event"].level == EventLevel.info


def test_danmu_unexpected_failure_event_stays_error(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        workflow_event_emitters.event_service,
        "emit_media",
        lambda event, meta=None: captured.setdefault("event", event),
    )

    workflow_event_emitters.emit_danmu_generate_event(
        EventType.DANMU_GENERATE_FAILED,
        _media(),
        Path("/data/Test Show S01E01.mkv"),
        1,
        "action-1",
        "task-1",
        error="provider failed",
    )

    assert captured["event"].level == EventLevel.error
