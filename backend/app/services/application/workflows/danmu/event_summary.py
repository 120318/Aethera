from pathlib import Path

from pydantic import BaseModel

from app.schemas.domain.action import ActionStatus
from app.schemas.domain.addon_events import DanmuGenerationOutcome, ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.event import EventActor, EventType
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaFullInfo
from app.services.audit.workflow_event_emitters import emit_danmu_generate_event
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file


class DanmuImportBatch(BaseModel):
    imported_files: list[ImportedMediaFile]
    library_files_by_path: dict[str, LibraryFile]


def resolve_primary_import_batch(
    meta: MediaImportCompletedEventMeta,
    library_files: list[LibraryFile],
) -> DanmuImportBatch:
    library_files_by_path = {
        str(build_library_file_path(item.path, item.file_name)): item
        for item in library_files
        if item.id
    }
    event_files = meta.imported_files or [
        ImportedMediaFile(destination_path=meta.file_path, episode_number=None)
    ]
    return DanmuImportBatch(
        imported_files=[
            item for item in event_files
            if item.destination_path in library_files_by_path
            and file_name_looks_like_media_file(library_files_by_path[item.destination_path].file_name)
        ],
        library_files_by_path=library_files_by_path,
    )


def emit_generation_summary(
    media: MediaFullInfo,
    outcomes: list[DanmuGenerationOutcome],
    *,
    actor: EventActor = EventActor.system,
) -> None:
    for status, event_type in (
        (ActionStatus.completed, EventType.DANMU_GENERATE_COMPLETED),
        (ActionStatus.failed, EventType.DANMU_GENERATE_FAILED),
    ):
        matching = [outcome for outcome in outcomes if outcome.status == status]
        if not matching:
            continue
        anchor = matching[0]
        providers = {outcome.provider for outcome in matching if outcome.provider}
        emit_danmu_generate_event(
            event_type,
            media,
            Path(anchor.video_path),
            anchor.episode_number if len(matching) == 1 else None,
            anchor.action_id,
            anchor.task_id,
            provider=next(iter(providers)) if len(providers) == 1 else None,
            xml_path=Path(anchor.xml_path) if anchor.xml_path else None,
            ass_path=Path(anchor.ass_path) if anchor.ass_path else None,
            error=anchor.error,
            video_paths=[Path(outcome.video_path) for outcome in matching],
            episode_numbers=[outcome.episode_number for outcome in matching if outcome.episode_number],
            actor=actor,
        )
