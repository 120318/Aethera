from __future__ import annotations

import shutil
from pathlib import Path

from app.core.storage_paths import get_download_root
from app.schemas.domain.download import DownloadInfo, TaskData
from app.services.config.settings_service import settings_service
from app.utils.library_paths import build_download_path


def delete_download_content_for_task(task: TaskData, info: DownloadInfo | None) -> bool:
    target = resolve_download_content_delete_target(task, info)
    if not target:
        return False
    return delete_download_content_path(target)


def resolve_download_content_delete_target(task: TaskData, info: DownloadInfo | None) -> Path | None:
    target = _resolve_task_content_path(info)
    if not target:
        return None
    if not target.exists():
        return target
    if not _is_safe_download_content_target(task, target):
        return None
    return target


def delete_download_content_path(target: Path) -> bool:
    if not target.exists():
        return True
    try:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            return False
    except OSError:
        return False
    return True


def _resolve_task_content_path(info: DownloadInfo | None) -> Path | None:
    content_path = (info.content_path if info else "") or ""
    if not content_path:
        return None
    return build_download_path(content_path).resolve(strict=False)


def _is_safe_download_content_target(task: TaskData, target: Path) -> bool:
    allowed_roots = _allowed_download_roots(task)
    for root in allowed_roots:
        if target == root:
            continue
        try:
            target.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _allowed_download_roots(task: TaskData) -> list[Path]:
    roots = [get_download_root().resolve(strict=False)]
    directory_id = task.context.directory_id if task.context else None
    if directory_id:
        directory = settings_service.get_directory_by_id(directory_id)
        if directory and directory.download_path:
            roots.insert(0, build_download_path(directory.download_path).resolve(strict=False))
    return roots
