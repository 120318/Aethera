from __future__ import annotations

import logging
from pathlib import Path

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskData
from app.schemas.domain.torrent import TorrentFileItem
from app.services.domain.directory_integrity.models import DirectorySizeIndex, DirectorySizeSummary
from app.utils.library_paths import build_download_path

logger = logging.getLogger("app.services.directory_integrity.size_summary")


def build_directory_size_index(
    directories: list[DirectoryConfig],
    tasks: list[TaskData],
    all_directories: list[DirectoryConfig],
) -> DirectorySizeIndex:
    global_inodes: set[tuple[int, int]] = set()
    global_paths: set[str] = set()
    download_roots_by_directory_id = _build_download_root_index(all_directories)
    directory_sizes: dict[str, DirectorySizeSummary] = {}
    global_summary = DirectorySizeSummary()
    for directory in directories:
        directory_sizes[directory.id] = _directory_size_summary(directory, tasks, download_roots_by_directory_id)
        global_summary = _add_size_summary(
            global_summary,
            _directory_size_summary(
                directory,
                tasks,
                download_roots_by_directory_id,
                seen_inodes=global_inodes,
                seen_paths=global_paths,
            ),
        )
    return DirectorySizeIndex(directories=directory_sizes, global_summary=global_summary)


def _directory_size_summary(
    directory: DirectoryConfig,
    tasks: list[TaskData],
    download_roots_by_directory_id: dict[str, str],
    *,
    seen_inodes: set[tuple[int, int]] | None = None,
    seen_paths: set[str] | None = None,
) -> DirectorySizeSummary:
    inode_index = seen_inodes if seen_inodes is not None else set()
    path_index = seen_paths if seen_paths is not None else set()
    library_size, library_physical_size = _root_size_summary(directory.path, inode_index, path_index)
    download_size, download_physical_size = _task_download_size_summary(
        directory,
        tasks,
        download_roots_by_directory_id,
        inode_index,
        path_index,
    )
    return DirectorySizeSummary(
        physical_size=library_physical_size + download_physical_size,
        logical_size=library_size + download_size,
        library_logical_size=library_size,
        download_logical_size=download_size,
    )


def _task_download_size_summary(
    directory: DirectoryConfig,
    tasks: list[TaskData],
    download_roots_by_directory_id: dict[str, str],
    seen_inodes: set[tuple[int, int]],
    seen_paths: set[str],
) -> tuple[int, int]:
    logical_size = 0
    physical_size = 0
    for task in tasks:
        if not task.context or task.context.directory_id != directory.id:
            continue
        if task.context.directory_id not in download_roots_by_directory_id:
            continue
        for path in _task_existing_download_files(task):
            item_logical_size, item_physical_size = _file_size_summary(path, seen_inodes, seen_paths)
            logical_size += item_logical_size
            physical_size += item_physical_size
    return (logical_size, physical_size)


def _task_existing_download_files(task: TaskData) -> list[Path]:
    base = build_download_path(task.save_path)
    if not task.metadata or not task.metadata.files:
        return _existing_files_under(base)
    paths: list[Path] = []
    torrent_name = str(task.metadata.name or "").strip()
    for file_item in _selected_metadata_files(task):
        candidates = _download_file_candidates(base, torrent_name, file_item)
        existing = next((path for path in candidates if path.exists() and path.is_file()), None)
        if existing:
            paths.append(existing)
    return paths


def _existing_files_under(path: Path) -> list[Path]:
    if path.exists() and path.is_file():
        return [path]
    if path.exists() and path.is_dir():
        return _iter_files(path)
    return []


def _selected_metadata_files(task: TaskData) -> list[TorrentFileItem]:
    if not task.metadata or not task.metadata.files:
        return []
    selected = set(task.context.selected_files or []) if task.context and task.context.selected_files else None
    return [
        file_item
        for index, file_item in enumerate(task.metadata.files)
        if selected is None or index in selected
    ]


def _download_file_candidates(base: Path, torrent_name: str, file_item: TorrentFileItem) -> list[Path]:
    direct_path = base / file_item.filename
    candidates = [direct_path]
    if torrent_name and Path(file_item.filename).parts[:1] != (torrent_name,):
        candidates.append(base / torrent_name / file_item.filename)
    return candidates


def _root_size_summary(root_path: str, seen_inodes: set[tuple[int, int]], seen_paths: set[str]) -> tuple[int, int]:
    root = _resolve_existing_root(root_path)
    if not root:
        return (0, 0)
    logical_size = 0
    physical_size = 0
    for path in _iter_files(root):
        try:
            stat = path.stat()
        except OSError:
            continue
        item_logical_size, item_physical_size = _stat_size_summary(path, stat, seen_inodes, seen_paths)
        logical_size += item_logical_size
        physical_size += item_physical_size
    return (logical_size, physical_size)


def _file_size_summary(path: Path, seen_inodes: set[tuple[int, int]], seen_paths: set[str]) -> tuple[int, int]:
    try:
        stat = path.stat()
    except OSError:
        return (0, 0)
    return _stat_size_summary(path, stat, seen_inodes, seen_paths)


def _stat_size_summary(path: Path, stat, seen_inodes: set[tuple[int, int]], seen_paths: set[str]) -> tuple[int, int]:
    logical_size = 0
    physical_size = 0
    path_key = _normalize_path(path)
    if path_key not in seen_paths:
        seen_paths.add(path_key)
        logical_size = stat.st_size
    inode_key = (stat.st_dev, stat.st_ino)
    if inode_key not in seen_inodes:
        seen_inodes.add(inode_key)
        physical_size = _stat_physical_size(stat)
    return (logical_size, physical_size)


def _build_download_root_index(directories: list[DirectoryConfig]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for directory in directories:
        root = _resolve_existing_root(directory.download_path)
        if root:
            roots[directory.id] = _normalize_path(root)
    return roots


def _add_size_summary(left: DirectorySizeSummary, right: DirectorySizeSummary) -> DirectorySizeSummary:
    return DirectorySizeSummary(
        physical_size=left.physical_size + right.physical_size,
        logical_size=left.logical_size + right.logical_size,
        library_logical_size=left.library_logical_size + right.library_logical_size,
        download_logical_size=left.download_logical_size + right.download_logical_size,
    )


def _resolve_existing_root(path: str) -> Path | None:
    value = str(path or "").strip()
    if not value:
        return None
    root = Path(value).resolve(strict=False)
    return root if root.exists() and root.is_dir() else None


def _iter_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    try:
        candidates = root.rglob("*")
        for path in candidates:
            if _should_skip_path(root, path):
                continue
            if path.is_file():
                paths.append(path)
    except OSError as exc:
        logger.warning("Failed to inspect directory size for %s: %s", root, exc)
    return paths


def _should_skip_path(root: Path, path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return False
    except ValueError:
        return True


def _normalize_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def _stat_physical_size(stat) -> int:
    try:
        blocks = stat.st_blocks
    except AttributeError:
        return stat.st_size
    return int(blocks) * 512 if blocks else stat.st_size
