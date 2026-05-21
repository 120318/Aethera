from app.schemas.domain.action import ActionKind, ActionName, ActionRecord, ActionStatus
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import (
    DanmuGenerateEventMeta,
    DownloadTaskEventMeta,
    ImportedMediaFile,
    MediaDeletedEventMeta,
    MediaImportCompletedEventMeta,
    MediaServerSyncEventMeta,
)
from app.schemas.domain.download import TaskStatus
from app.schemas.domain.event import MediaEventCreate
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.audit.action_message_i18n import attach_action_message_i18n
from app.services.audit.event_message_i18n import event_message_key, event_message_params
from app.services.audit.search_text_support import build_action_search_text
from app.services.i18n.message_renderer import render_message


def _media() -> MediaIdentity:
    return MediaIdentity(media_id=MediaID.parse("tmdb:movie:1"), title="Test Movie", year=2026)


def test_render_message_resolves_nested_error_key_params():
    message = render_message(
        "eventMessages.downloadFailed",
        {
            "title": "Test Show",
            "error_key": "backendErrors.seasonRequired",
        },
        locale="zh-CN",
    )

    assert "Test Show" in message
    assert "backendErrors.seasonRequired" not in message


def test_action_search_text_includes_rendered_command_message():
    action = ActionRecord(
        kind=ActionKind.command,
        action_name=ActionName.resource_search.value,
        status=ActionStatus.completed,
        message_params={"result_count": "3"},
    )
    attach_action_message_i18n(action)

    search_text = build_action_search_text(action)

    assert "commandmessages.resourcesearch.succeeded" in search_text
    assert "resource search" in search_text


def test_download_event_message_uses_resource_title():
    event = MediaEventCreate(type=EventTypes.DOWNLOAD_STARTED, media=_media(), task_id="task-1")
    params = event_message_params(
        event,
        DownloadTaskEventMeta(
            task_id="task-1",
            media_id=_media().media_id,
            status=TaskStatus.DOWNLOADING,
            resource_title="Partner.2026.2160p.WEB-DL",
            torrent_name="Partner.2026.2160p.WEB-DL",
            selected_files=[0],
            total_files=2,
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="en-US")

    assert "Partner.2026.2160p.WEB-DL" in message
    assert "Test Movie" not in message


def test_download_event_message_prefers_torrent_name_over_resource_title():
    event = MediaEventCreate(type=EventTypes.DOWNLOAD_STARTED, media=_media(), task_id="task-1")
    params = event_message_params(
        event,
        DownloadTaskEventMeta(
            task_id="task-1",
            media_id=_media().media_id,
            status=TaskStatus.DOWNLOADING,
            resource_title="Low IQ Crime",
            torrent_name="Low.IQ.Crime.2025.2160p.WEB-DL",
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="zh-CN")

    assert "Low.IQ.Crime.2025.2160p.WEB-DL" in message
    assert "Low IQ Crime" not in message


def test_media_import_event_message_includes_first_file_name():
    event = MediaEventCreate(type=EventTypes.MEDIA_IMPORT_COMPLETED, media=_media(), task_id="task-1")
    params = event_message_params(
        event,
        MediaImportCompletedEventMeta(
            task_id="task-1",
            directory_id="dir-1",
            media_id=_media().media_id,
            resource_title="Partner.2026.2160p.WEB-DL",
            imported_files=[
                ImportedMediaFile(destination_path="/library/Partner (2026)/Partner.2026.mkv"),
            ],
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="en-US")

    assert "Partner.2026.mkv" in message
    assert "1 files" in message


def test_media_server_sync_message_includes_target_file_name():
    event = MediaEventCreate(type=EventTypes.MEDIA_SERVER_SYNC_STARTED, media=_media(), task_id="task-1")
    params = event_message_params(
        event,
        MediaServerSyncEventMeta(
            media_id=_media().media_id,
            media_server_id="jellyfin",
            file_path="/library/Partner (2026)/Partner.2026.mkv",
            trigger="manual",
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="zh-CN")

    assert "Partner.2026.mkv" in message


def test_danmu_event_message_includes_video_file_name():
    event = MediaEventCreate(type=EventTypes.DANMU_GENERATE_STARTED, media=_media(), task_id="task-1")
    params = event_message_params(
        event,
        DanmuGenerateEventMeta(
            media_id=_media().media_id,
            video_path="/library/Partner (2026)/Partner.2026.mkv",
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="zh-CN")

    assert "Partner.2026.mkv" in message


def test_media_deleted_event_message_includes_first_deleted_target():
    event = MediaEventCreate(type=EventTypes.MEDIA_DELETED, media=_media())
    params = event_message_params(
        event,
        MediaDeletedEventMeta(
            media_id=_media().media_id,
            directory_id="dir-1",
            paths=["/library/Partner (2026)/Partner.2026.mkv"],
            delete_scope="file",
        ),
    )

    message = render_message(event_message_key(event.type), params, locale="en-US")

    assert "Partner.2026.mkv" in message
    assert "1 paths" in message
