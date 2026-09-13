from __future__ import annotations

from pathlib import Path

from app.schemas.domain.download import DownloadFileInfo, TaskData, TaskStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.services.domain.download import download_service
from app.services.domain.library.target_path_policy import library_target_path_policy
from app.services.domain.resource.filtering import is_original_disc_attrs
from app.utils.library_paths import file_name_looks_like_media_file

from .execution import (
    TransferExecutionContext,
    build_source_path,
    build_transfer_planning_context,
    iter_selected_files,
    with_context_resource_attrs,
)


EARLY_IMPORT_TASK_STATUSES = {TaskStatus.DOWNLOADING, TaskStatus.PAUSED}
READABLE_TORRENT_STATES = {
    TorrentState.DOWNLOADING,
    TorrentState.PAUSED,
    TorrentState.SEEDING,
}


def supports_episode_batch_import(task: TaskData) -> bool:
    metadata = task.metadata
    if task.status not in EARLY_IMPORT_TASK_STATUSES:
        return False
    if task.media_id.media_type != MediaType.tv or metadata is None or not metadata.files:
        return False
    if metadata.is_disc_package() or (metadata.attrs and is_original_disc_attrs(metadata.attrs)):
        return False
    return not any(
        (item.attrs and is_original_disc_attrs(item.attrs))
        or Path(item.filename).suffix.lower() in {".iso", ".bdmv", ".ifo"}
        for item in metadata.files
    )


def selected_file_indices(task: TaskData) -> set[int]:
    if task.metadata is None:
        return set()
    selected = set(task.context.selected_files) if task.context.selected_files else None
    return {index for index, _item in iter_selected_files(task.metadata.files, selected)}


def remaining_selected_file_indices(task: TaskData) -> set[int]:
    return selected_file_indices(task) - set(task.context.imported_file_indices)


def _torrent_relative_path(task: TaskData, filename: str) -> Path:
    relative = Path(filename)
    root_name = Path(task.metadata.name).name if task.metadata else ""
    if relative.parts and root_name and relative.parts[0] == root_name:
        return Path(*relative.parts[1:])
    return relative


def _live_file_is_ready(task: TaskData, item: TorrentFileItem, live: DownloadFileInfo, source_base: Path) -> bool:
    if not live.is_selected or live.priority <= 0 or live.progress < 1.0:
        return False
    if item.size <= 0 or live.size != item.size:
        return False
    if _torrent_relative_path(task, live.name) != _torrent_relative_path(task, item.filename):
        return False
    source_path = build_source_path(task, item, source_base)
    try:
        return source_path.is_file() and source_path.stat().st_size == item.size
    except OSError:
        return False


async def has_episode_target_collisions(task: TaskData, context: TransferExecutionContext | None = None) -> bool:
    if task.metadata is None:
        return False
    context = context or await build_transfer_planning_context(task)
    paths: set[Path] = set()
    for _index, original_item in iter_selected_files(task.metadata.files, context.selected_indices):
        if not file_name_looks_like_media_file(original_item.filename):
            continue
        item = with_context_resource_attrs(task, original_item)
        destination = library_target_path_policy.build_destination_path(
            destination_base_path=context.destination_base_path,
            template_config=context.template_config,
            title=context.title,
            year=context.year,
            season_number=context.season_number,
            file_item=item,
        )
        if destination in paths:
            return True
        paths.add(destination)
    return False


async def find_ready_episode_file_indices(task: TaskData, status: TorrentStatus | None) -> list[int]:
    if not supports_episode_batch_import(task) or status is None:
        return []
    if not status.files_readable or status.state not in READABLE_TORRENT_STATES:
        return []

    context = await build_transfer_planning_context(task)
    if not status.save_path:
        return []
    if Path(status.save_path).resolve(strict=False) != context.source_base_path.resolve(strict=False):
        return []
    if await has_episode_target_collisions(task, context):
        return []

    live_files = await download_service.get_task_torrent_files(task)
    if not live_files:
        return []
    live_by_index = {item.index: item for item in live_files}
    imported = set(task.context.imported_file_indices)
    ready: list[int] = []
    for index, item in iter_selected_files(task.metadata.files, context.selected_indices):
        if index in imported or not file_name_looks_like_media_file(item.filename):
            continue
        live = live_by_index.get(index)
        if live and _live_file_is_ready(task, item, live, context.source_base_path):
            ready.append(index)
    return sorted(ready)
