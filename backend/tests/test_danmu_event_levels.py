from pathlib import Path

from app.schemas.domain.action import ActionStatus
from app.schemas.domain.addon_events import DanmuGenerationOutcome
from app.schemas.domain.event import EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.audit import workflow_event_emitters
from app.services.application.workflows.danmu import event_summary


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


def test_danmu_skipped_outcomes_do_not_emit_events(monkeypatch):
    emitted = []
    monkeypatch.setattr(event_summary, "emit_danmu_generate_event", lambda *args, **kwargs: emitted.append(args))

    event_summary.emit_generation_summary(
        _media(),
        [
            DanmuGenerationOutcome(
                status=ActionStatus.skipped,
                video_path="/data/Test Show S01E01.mkv",
                episode_number=1,
                action_id="action-1",
                task_id="task-1",
            )
        ],
    )

    assert emitted == []


def test_danmu_multiple_failures_emit_one_summary_event(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        event_summary,
        "emit_danmu_generate_event",
        lambda *args, **kwargs: emitted.append((args, kwargs)),
    )

    event_summary.emit_generation_summary(
        _media(),
        [
            DanmuGenerationOutcome(
                status=ActionStatus.failed,
                video_path=f"/data/Test Show S01E0{episode}.mkv",
                episode_number=episode,
                action_id=f"action-{episode}",
                task_id="task-1",
                error="provider failed",
            )
            for episode in (1, 2, 3)
        ],
    )

    assert len(emitted) == 1
    assert emitted[0][0][0] == EventType.DANMU_GENERATE_FAILED
    assert emitted[0][1]["episode_numbers"] == [1, 2, 3]
    assert len(emitted[0][1]["video_paths"]) == 3
