from __future__ import annotations

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_types import MediaType
from app.services.domain.download.coverage import resolve_task_episode_coverage_detail
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file


def task_library_relationship_is_satisfied(
    task: TaskData,
    directory_id: str,
    audit_statuses: set[TaskStatus],
    files_by_task_id: dict[str, list[LibraryFile]],
    directory_files: list[LibraryFile],
) -> bool:
    return bool(
        task.context.directory_id != directory_id
        or task.status not in audit_statuses
        or task.id in files_by_task_id
        or is_task_fully_replaced(task, directory_files)
    )


def is_task_fully_replaced(task: TaskData, directory_files: list[LibraryFile]) -> bool:
    if not task.metadata or not task.metadata.files:
        return False
    selected = set(task.context.selected_files) if task.context.selected_files else None
    primary_indices = {
        item.index
        for item in task.metadata.files
        if (selected is None or item.index in selected)
        and file_name_looks_like_media_file(item.filename)
    }
    if not primary_indices or not primary_indices.issubset(set(task.context.imported_file_indices)):
        return False

    visible_replacements = []
    for item in directory_files:
        if (
            item.task_id == task.id
            or item.media_id != task.media_id
            or not file_name_looks_like_media_file(item.file_name or "")
        ):
            continue
        try:
            if build_library_file_path(item.path, item.file_name).is_file():
                visible_replacements.append(item)
        except OSError:
            continue
    if not visible_replacements:
        return False
    if task.media_id.media_type != MediaType.tv:
        return True

    coverage = resolve_task_episode_coverage_detail(task)
    if not coverage.has_known_season or not coverage.episode_numbers:
        return False
    visible_episodes: set[int] = set()
    for item in visible_replacements:
        attrs = item.resource_attributes
        if attrs.seasons and coverage.season_number not in attrs.seasons:
            continue
        visible_episodes.update(int(value) for value in attrs.episodes if int(value) > 0)
    return set(coverage.episode_numbers).issubset(visible_episodes)
