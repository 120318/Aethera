from dataclasses import dataclass
from pathlib import Path

from app.schemas.domain.download import DownloadInfoLookupStatus, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.filtering import is_original_disc_attrs
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file

from .execution import build_source_path, iter_selected_files, resolve_selected_indices, resolve_source_base_path
from .replacement import library_replacement_policy


ACTIVE_IMPORT_STATUSES = [TaskStatus.DOWNLOADING, TaskStatus.PAUSED]
# Checking, allocating, moving, metadata and error states cannot publish files.
READABLE_TORRENT_STATES = {
    TorrentState.DOWNLOADING.value, TorrentState.PAUSED.value,
    TorrentState.SEEDING.value, TorrentState.QUEUED.value,
    "downloading", "stalleddl", "forceddl", "pauseddl", "stoppeddl", "queueddl",
    "uploading", "stalledup", "forcedup", "pausedup", "stoppedup", "queuedup",
}


@dataclass(frozen=True)
class ReadyFileInspection:
    indices: list[int]
    can_become_ready: bool
    source_fallback_allowed: bool = False


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


def _imported_episode_groups(task: TaskData) -> set[frozenset[int]]:
    groups: set[frozenset[int]] = set()
    if not task.metadata:
        return groups
    imported = set(task.context.imported_file_indices)
    for item in task.metadata.files:
        if item.index not in imported or not file_name_looks_like_media_file(item.filename):
            continue
        group = frozenset(int(value) for value in item.get_episodes() if int(value) > 0)
        if group:
            groups.add(group)
    return groups


async def satisfied_file_indices(task: TaskData, existing_files: list[LibraryFile]) -> set[int]:
    satisfied = present_file_indices(existing_files)
    imported_episode_groups = _imported_episode_groups(task)
    if not imported_episode_groups:
        return satisfied
    coverage = download_service.resolve_task_episode_coverage_detail(task)
    satisfied.update(
        await library_replacement_policy.satisfied_file_indices(
            task,
            coverage.season_number,
            imported_episode_groups,
        )
    )
    return satisfied


def _torrent_relative_path(task: TaskData, filename: str) -> Path:
    relative = Path(filename)
    root_name = Path(task.metadata.name).name
    if relative.parts and root_name and relative.parts[0] == root_name:
        return Path(*relative.parts[1:])
    return relative


async def inspect_ready_files(
    task: TaskData,
    existing_files: list[LibraryFile],
    torrent_status: TorrentStatus | None = None,
    known_satisfied_indices: set[int] | None = None,
) -> ReadyFileInspection:
    if task.status not in [*ACTIVE_IMPORT_STATUSES, TaskStatus.FINISHED] or not supports_early_import(task):
        return ReadyFileInspection([], False)
    client = download_service.task_service.resolve_task_client(task)
    if client is None:
        return ReadyFileInspection([], True)
    if torrent_status is not None:
        info = torrent_status
    else:
        lookup = await client.lookup_torrent_info(task.torrent_hash)
        if lookup.status == DownloadInfoLookupStatus.MISSING:
            return ReadyFileInspection([], False, True)
        if lookup.status == DownloadInfoLookupStatus.UNAVAILABLE or lookup.info is None:
            return ReadyFileInspection([], True)
        info = lookup.info
    if not info.files_readable:
        return ReadyFileInspection([], True)
    if info.state.lower() not in READABLE_TORRENT_STATES:
        can_become_ready = info.state.lower() in {
            "checkingdl", "checkingup", "checkingresumedata", "moving", "allocating", "checking",
        }
        return ReadyFileInspection([], can_become_ready)
    source_base = await resolve_source_base_path(task)
    if Path(info.save_path).resolve() != source_base.resolve():
        return ReadyFileInspection([], False)
    live_files = await client.get_torrent_files(task.torrent_hash)
    if live_files is None:
        return ReadyFileInspection([], True)
    if not live_files:
        return ReadyFileInspection([], False)
    live_by_index = {item.index: item for item in live_files}
    imported = (
        known_satisfied_indices
        if known_satisfied_indices is not None
        else await satisfied_file_indices(task, existing_files)
    )
    ready: list[int] = []
    can_become_ready = task.status in ACTIVE_IMPORT_STATUSES
    for index, item in iter_selected_files(task.metadata.files, resolve_selected_indices(task)):
        if task.status in ACTIVE_IMPORT_STATUSES and not file_name_looks_like_media_file(item.filename):
            continue
        live = live_by_index.get(index)
        if index in imported or live is None or live.priority <= 0:
            continue
        if live.progress != 1.0:
            can_become_ready = True
            continue
        if item.size <= 0 or live.size != item.size:
            continue
        source = build_source_path(task, item, source_base)
        # A renamed file or an incomplete/temp directory needs a fresh path mapping,
        # not an attempt to import an unrelated file at the old metadata path.
        if _torrent_relative_path(task, live.name) != _torrent_relative_path(task, item.filename):
            continue
        try:
            if source.is_file() and source.stat().st_size == item.size:
                ready.append(index)
        except OSError:
            continue
    return ReadyFileInspection(ready, can_become_ready)


async def ready_file_indices(
    task: TaskData,
    existing_files: list[LibraryFile],
    torrent_status: TorrentStatus | None = None,
) -> list[int]:
    return (await inspect_ready_files(task, existing_files, torrent_status)).indices


async def find_ready_file_indices(task: TaskData, torrent_status: TorrentStatus | None = None) -> list[int]:
    if not supports_early_import(task):
        return []
    return await ready_file_indices(task, await library_service.get_files_by_task(task.id), torrent_status)
