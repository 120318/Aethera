from pathlib import Path

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_types import MediaType
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.filtering import is_original_disc_attrs
from app.utils.library_paths import build_library_file_path

from .execution import build_source_path, iter_selected_files, resolve_selected_indices, resolve_source_base_path


ACTIVE_IMPORT_STATUSES = [TaskStatus.DOWNLOADING, TaskStatus.PAUSED]
# Checking, allocating, moving, metadata and error states cannot publish files.
READABLE_TORRENT_STATES = {
    "downloading", "stalleddl", "forceddl", "pauseddl", "stoppeddl", "queueddl",
    "uploading", "stalledup", "forcedup", "pausedup", "stoppedup", "queuedup",
}


def supports_early_import(task: TaskData) -> bool:
    metadata = task.metadata
    return bool(
        task.media_id.media_type == MediaType.tv
        and metadata and metadata.files
        and not metadata.is_disc_package()
        and not (metadata.attrs and is_original_disc_attrs(metadata.attrs))
        and not any(
            (item.attrs and is_original_disc_attrs(item.attrs))
            or Path(item.filename).suffix.lower() in {".iso", ".bdmv", ".ifo"}
            for item in metadata.files
        )
    )


def present_file_indices(files: list[LibraryFile]) -> set[int]:
    present: set[int] = set()
    for item in files:
        if item.file_index is None:
            continue
        path = build_library_file_path(item.path, item.file_name)
        try:
            if path.is_file():
                present.add(item.file_index)
        except OSError:
            continue
    return present


async def ready_file_indices(task: TaskData, existing_files: list[LibraryFile]) -> list[int]:
    if task.status not in [*ACTIVE_IMPORT_STATUSES, TaskStatus.FINISHED] or not supports_early_import(task):
        return []
    client = download_service.task_service.resolve_task_client(task)
    if client is None:
        return []
    info = await client.get_torrent_info(task.torrent_hash)
    if info is None or info.state.lower() not in READABLE_TORRENT_STATES:
        return []
    source_base = await resolve_source_base_path(task)
    if Path(info.save_path).resolve() != source_base.resolve():
        return []
    live_files = await client.get_torrent_files(task.torrent_hash)
    if not live_files:
        return []
    live_by_index = {item.index: item for item in live_files}
    imported = present_file_indices(existing_files)
    ready: list[int] = []
    for index, item in iter_selected_files(task.metadata.files, resolve_selected_indices(task)):
        live = live_by_index.get(index)
        if index in imported or live is None or live.priority <= 0 or live.progress != 1.0:
            continue
        if item.size <= 0 or live.size != item.size:
            continue
        source = build_source_path(task, item, source_base)
        # A renamed file or an incomplete/temp directory needs a fresh path mapping,
        # not an attempt to import an unrelated file at the old metadata path.
        if (source_base / live.name).resolve() != source.resolve():
            continue
        try:
            if source.is_file() and source.stat().st_size == item.size:
                ready.append(index)
        except OSError:
            continue
    return ready


async def find_ready_file_indices(task: TaskData) -> list[int]:
    if not supports_early_import(task):
        return []
    return await ready_file_indices(task, await library_service.get_files_by_task(task.id))
