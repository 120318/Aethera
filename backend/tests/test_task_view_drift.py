import os
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

pytestmark = [pytest.mark.drift, pytest.mark.health]

from app.schemas.media_id import MediaID
from app.schemas.domain.command import CommandRecord, CommandTargetType, CommandType, TaskTransferCommandRecordPayload
from app.schemas.domain.download import TaskContext, TaskData, TaskErrorStage, TaskStatus
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.resource_attributes import PackageLayoutValue, ResourceAttributes, ResourceFormEvidence
from app.schemas.domain.torrent import TorrentMetadata
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.schemas.runtime.task_view import TaskAction, TaskPhase, TaskPhaseGroup
from app.services.application.views.task import TaskViewService


def _task(status: TaskStatus, *, progress: float = 1.0, error_stage: TaskErrorStage | None = None) -> TaskData:
    media_id = MediaID.parse("tmdb:tv:1")
    return TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=status,
        progress=progress,
        error_stage=error_stage,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Show", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _torrent_status(state: TorrentState) -> TorrentStatus:
    return TorrentStatus(
        hash="hash-1",
        name="Example",
        size=1,
        progress=0.5,
        state=state,
        downloader_id="downloader-1",
    )


def _active_task_command(task: TaskData, command_type: CommandType = CommandType.TASK_TRANSFER) -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id="command-1",
        type=command_type,
        payload=TaskTransferCommandRecordPayload(
            resolved_task_id=task.id,
            target=MediaTarget(media_id=media_id, season_number=1),
        ),
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        target_type=CommandTargetType.TASK,
        target_id=task.id,
    )


def _action_state(view, action: TaskAction):
    return next(item for item in view.action_states if item.action == action)


def test_build_task_view_marks_seeding_absent_as_attention_with_delete_only_actions():
    service = TaskViewService()
    task = _task(TaskStatus.SEEDING_ABSENT)

    view = service._build_task_view(task, realtime=None, active_command=None, has_primary_library_files=False)

    assert view.phase == TaskPhase.ATTENTION
    assert view.phase_group == TaskPhaseGroup.ATTENTION
    assert view.phase_label_key == "taskStatus.status.seedingAbsent"
    assert view.media_type == "tv"
    assert view.media_id == "tmdb:tv:1"
    assert view.attention_reason_key == "taskStatus.warning.seedingAbsent"
    assert view.actions == [TaskAction.VIEW_DETAIL, TaskAction.DELETE]
    assert [item.action for item in view.action_states if item.available] == view.actions


def test_build_task_view_resolves_pause_and_resume_from_realtime_state():
    service = TaskViewService()
    task = _task(TaskStatus.DOWNLOADING)

    downloading_view = service._build_task_view(
        task,
        realtime=_torrent_status(TorrentState.DOWNLOADING),
        active_command=None,
        has_primary_library_files=False,
    )
    paused_view = service._build_task_view(
        task,
        realtime=_torrent_status(TorrentState.PAUSED),
        active_command=None,
        has_primary_library_files=False,
    )

    assert TaskAction.PAUSE in downloading_view.actions
    assert TaskAction.RESUME not in downloading_view.actions
    assert TaskAction.RESUME in paused_view.actions
    assert TaskAction.PAUSE not in paused_view.actions


def test_build_task_view_allows_manual_transfer_for_file_missing_task():
    service = TaskViewService()
    task = _task(TaskStatus.FILE_MISSING)

    view = service._build_task_view(task, realtime=None, active_command=None, has_primary_library_files=False)

    assert view.phase == TaskPhase.ATTENTION
    assert view.phase_label_key == "taskStatus.status.fileMissing"
    assert TaskAction.TRANSFER in view.actions
    assert TaskAction.DELETE in view.actions


def test_build_task_view_exposes_post_transfer_actions_when_library_files_exist():
    service = TaskViewService()
    task = _task(TaskStatus.COMPLETED)

    view = service._build_task_view(
        task,
        realtime=None,
        active_command=None,
        has_primary_library_files=True,
        can_media_server_sync=True,
        can_danmu_generate=True,
    )

    assert TaskAction.MEDIA_SERVER_SYNC in view.actions
    assert TaskAction.DANMU_GENERATE in view.actions


def test_build_task_view_hides_unavailable_post_transfer_actions():
    service = TaskViewService()
    task = _task(TaskStatus.COMPLETED)

    view = service._build_task_view(task, realtime=None, active_command=None, has_primary_library_files=True)

    assert TaskAction.MEDIA_SERVER_SYNC not in view.actions
    assert TaskAction.DANMU_GENERATE not in view.actions


def test_build_task_view_marks_actions_loading_when_task_command_is_active():
    service = TaskViewService()
    task = _task(TaskStatus.COMPLETED)
    active_command = _active_task_command(task)

    view = service._build_task_view(
        task,
        realtime=None,
        active_command=active_command,
        has_primary_library_files=True,
        can_media_server_sync=True,
        can_danmu_generate=True,
    )

    detail_state = _action_state(view, TaskAction.VIEW_DETAIL)
    transfer_state = _action_state(view, TaskAction.TRANSFER)
    delete_state = _action_state(view, TaskAction.DELETE)
    sync_state = _action_state(view, TaskAction.MEDIA_SERVER_SYNC)

    assert detail_state.loading is False
    assert detail_state.disabled is False
    for state in [transfer_state, delete_state, sync_state]:
        assert state.loading is True
        assert state.disabled is True
        assert state.disabled_reason_key == "taskLive.taskProcessing"
        assert state.active_command_id == active_command.id
        assert state.active_command_type == active_command.type.value


def test_build_task_view_keeps_migrating_actions_visible_but_disabled():
    service = TaskViewService()
    task = _task(TaskStatus.MIGRATING)

    view = service._build_task_view(
        task,
        realtime=None,
        active_command=None,
        has_primary_library_files=True,
        can_media_server_sync=True,
        can_danmu_generate=True,
    )

    assert view.phase == TaskPhase.MIGRATING
    assert view.phase_group == TaskPhaseGroup.MIGRATING
    assert view.actions == [
        TaskAction.VIEW_DETAIL,
        TaskAction.TRANSFER,
        TaskAction.MEDIA_SERVER_SYNC,
        TaskAction.DANMU_GENERATE,
        TaskAction.CHANGE_DOWNLOADER,
        TaskAction.DELETE,
    ]
    for state in view.action_states:
        if state.action == TaskAction.VIEW_DETAIL:
            assert state.disabled is False
            continue
        assert state.available is True
        assert state.loading is False
        assert state.disabled is True
        assert state.disabled_reason_key == "taskLive.taskProcessing"


def test_build_task_view_allows_manual_transfer_for_transfer_error_after_download_completion():
    service = TaskViewService()
    task = _task(TaskStatus.ERROR, progress=1.0, error_stage=TaskErrorStage.TRANSFER)

    view = service._build_task_view(task, realtime=None, active_command=None, has_primary_library_files=False)

    assert view.phase == TaskPhase.FAILED
    assert view.attention_reason_key == "taskStatus.stage.transfer"
    assert TaskAction.TRANSFER in view.actions


def test_build_task_view_uses_torrent_structure_attributes_for_disc_package():
    service = TaskViewService()
    task = _task(TaskStatus.DOWNLOADING)
    task.context.parsed_attributes = ResourceAttributes(title="Example", sources=["WEB-DL"])
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Example",
        size=1,
        attrs=ResourceAttributes(
            title="Example",
            sources=["BluRay"],
            resource_form="BluRay Disc",
            resource_form_evidence=ResourceFormEvidence.TORRENT_STRUCTURE,
            package_layout=PackageLayoutValue.BDMV,
        ),
    )

    view = service._build_task_view(task, realtime=None, active_command=None, has_primary_library_files=False)

    assert view.attributes.resource_form == "BluRay Disc"
    assert view.attributes.resource_form_evidence == ResourceFormEvidence.TORRENT_STRUCTURE
    assert view.attributes.package_layout == PackageLayoutValue.BDMV
    assert "WEB-DL" in view.attributes.sources
    assert "BluRay" in view.attributes.sources


def test_task_matches_requested_season_from_task_media_context_when_parser_has_no_season():
    service = TaskViewService()
    task = _task(TaskStatus.DOWNLOADING)
    task.context.media = task.context.media.model_copy(update={"season_number": 2})

    assert service._task_matches_season(task, 2) is True
    assert service._task_matches_season(task, 1) is False
