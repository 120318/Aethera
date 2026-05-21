from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from pathlib import Path

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.domain.torrent_status import TorrentState
from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityIssueType,
    DirectoryIntegrityItem,
    DirectoryIntegrityPolicy,
    DirectoryIntegrityResult,
    DirectoryIntegrityScope,
)
from app.services.domain.directory_integrity.models import DirectoryIntegritySnapshot, DownloaderTorrentIndex, MediaDisplayIndex, TrackerMessageIndex
from app.services.domain.directory_integrity.size_summary import build_directory_size_index
from app.services.domain.directory_integrity.summary import build_directory_integrity_summary
from app.utils.library_paths import build_download_path, build_library_file_path, path_looks_like_media_file

logger = logging.getLogger("app.services.directory_integrity.scanner")

DOWNLOAD_AUDIT_STATUSES = {
    TaskStatus.FINISHED,
    TaskStatus.COMPLETED,
    TaskStatus.PARTIAL_MISSING,
    TaskStatus.SEEDING_ABSENT,
    TaskStatus.FILE_MISSING,
}
UNMANAGED_LIBRARY_FILE_GRACE_SECONDS = 600
MISSING_LIBRARY_FILE_GRACE_SECONDS = 600
TASK_MISSING_LIBRARY_FILE_GRACE_SECONDS = 600
TRANSIENT_DOWNLOAD_SUFFIXES = (
    ".!qb",
    ".part",
    ".parts",
)


class DirectoryIntegrityScanner:
    def scan(self, snapshot: DirectoryIntegritySnapshot, scan_id: str, scanned_at: float) -> DirectoryIntegrityResult:
        download_roots_by_directory_id = self._build_download_root_index(snapshot.all_directories)
        directory_sizes = build_directory_size_index(snapshot.directories, snapshot.tasks, snapshot.all_directories)
        items: list[DirectoryIntegrityItem] = []
        for directory in snapshot.directories:
            policy = self._policy_for_directory(snapshot.policies, directory.id)
            if not policy.enabled:
                continue
            allowed_issue_types = set(policy.issue_types)
            if policy.scan_library:
                library_items = self._scan_library_directory(
                    directory,
                    snapshot.library_files,
                    snapshot.tasks,
                    snapshot.media_display,
                    scanned_at,
                )
                items.extend(self._filter_by_policy(library_items, allowed_issue_types))
            if policy.scan_download:
                download_items = self._scan_download_directory(
                    directory,
                    snapshot.tasks,
                    download_roots_by_directory_id,
                    snapshot.downloader_torrents,
                    snapshot.media_display,
                )
                torrent_items = self._scan_downloader_torrents(
                    directory,
                    snapshot.tasks,
                    snapshot.downloader_torrents,
                    snapshot.tracker_messages,
                    snapshot.media_display,
                )
                items.extend(self._filter_by_policy(download_items, allowed_issue_types))
                items.extend(self._filter_by_policy(torrent_items, allowed_issue_types))
        return DirectoryIntegrityResult(
            scan_id=scan_id,
            scanned_at=scanned_at,
            summary=build_directory_integrity_summary(items, snapshot.directories, directory_sizes),
            items=items,
        )

    @staticmethod
    def _policy_for_directory(policies: dict[str, DirectoryIntegrityPolicy], directory_id: str) -> DirectoryIntegrityPolicy:
        return policies[directory_id] if directory_id in policies else DirectoryIntegrityPolicy.default_for_directory(directory_id)

    def _scan_library_directory(
        self,
        directory: DirectoryConfig,
        library_files: list[LibraryFile],
        tasks: list[TaskData],
        media_display: MediaDisplayIndex,
        scanned_at: float,
    ) -> list[DirectoryIntegrityItem]:
        root = self._resolve_existing_root(directory.path)
        if not root:
            return []
        directory_files = [item for item in library_files if item.directory_id == directory.id]
        expected = {self._normalize_path(build_library_file_path(item.path, item.file_name)): item for item in directory_files}
        items: list[DirectoryIntegrityItem] = []
        for file_path in self._iter_files(root):
            normalized = self._normalize_path(file_path)
            if normalized in expected or not path_looks_like_media_file(normalized):
                continue
            file_created_at = self._safe_created_at(file_path)
            if file_created_at and scanned_at - file_created_at < UNMANAGED_LIBRARY_FILE_GRACE_SECONDS:
                continue
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.unmanaged_library_file,
                    scope=DirectoryIntegrityScope.library,
                    directory=directory,
                    path=file_path,
                    root=root,
                    size=self._safe_size(file_path),
                    file_created_at=file_created_at,
                    repair_action="delete_file",
                )
            )
        for library_file in directory_files:
            path = build_library_file_path(library_file.path, library_file.file_name)
            if path.exists() or scanned_at - library_file.created_at < MISSING_LIBRARY_FILE_GRACE_SECONDS:
                continue
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.missing_library_file,
                    scope=DirectoryIntegrityScope.library,
                    directory=directory,
                    path=path,
                    root=root,
                    record_created_at=library_file.created_at,
                    library_file_name=library_file.file_name,
                    library_file_id=library_file.id,
                    task_id=library_file.task_id,
                    media_id=str(library_file.media_id),
                    media_display=self._media_display(media_display, str(library_file.media_id)),
                    repair_action="remove_library_record",
                )
            )
        items.extend(self._scan_library_task_relationships(directory, directory_files, tasks, root, media_display, scanned_at))
        return items

    def _scan_library_task_relationships(
        self,
        directory: DirectoryConfig,
        directory_files: list[LibraryFile],
        tasks: list[TaskData],
        root: Path,
        media_display: MediaDisplayIndex,
        scanned_at: float,
    ) -> list[DirectoryIntegrityItem]:
        files_by_task_id: dict[str, list[LibraryFile]] = {}
        for library_file in directory_files:
            if library_file.task_id not in files_by_task_id:
                files_by_task_id[library_file.task_id] = []
            files_by_task_id[library_file.task_id].append(library_file)
        task_ids = {task.id for task in tasks}
        items: list[DirectoryIntegrityItem] = []
        for task in tasks:
            if task.context.directory_id != directory.id or task.status not in DOWNLOAD_AUDIT_STATUSES or task.id in files_by_task_id:
                continue
            task_completed_at = self._datetime_to_timestamp(task.updated_at)
            if task_completed_at and scanned_at - task_completed_at < TASK_MISSING_LIBRARY_FILE_GRACE_SECONDS:
                continue
            media_id = str(task.media_id) if task.media_id else None
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.task_missing_library_file,
                    scope=DirectoryIntegrityScope.library,
                    directory=directory,
                    path=build_download_path(task.save_path),
                    root=root,
                    task_id=task.id,
                    task_completed_at=task_completed_at,
                    media_id=media_id,
                    display_name=self._task_context_label(task),
                    media_display=self._media_display(media_display, media_id),
                    repair_action="retry_transfer",
                    reason="task_has_no_library_file",
                )
            )
        for library_file in directory_files:
            if library_file.task_id in task_ids:
                continue
            path = build_library_file_path(library_file.path, library_file.file_name)
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.library_file_missing_task,
                    scope=DirectoryIntegrityScope.library,
                    directory=directory,
                    path=path,
                    root=root,
                    size=library_file.file_size,
                    library_file_id=library_file.id,
                    task_id=library_file.task_id,
                    media_id=str(library_file.media_id),
                    media_display=self._media_display(media_display, str(library_file.media_id)),
                    repair_action="remove_library_record",
                    reason="library_file_task_missing",
                )
            )
        return items

    def _scan_download_directory(
        self,
        directory: DirectoryConfig,
        tasks: list[TaskData],
        download_roots_by_directory_id: dict[str, str],
        downloader_torrents: DownloaderTorrentIndex,
        media_display: MediaDisplayIndex,
    ) -> list[DirectoryIntegrityItem]:
        root = self._resolve_existing_root(directory.download_path)
        if not root:
            return []
        root_key = self._normalize_path(root)
        root_tasks = [task for task in tasks if self._dict_value(download_roots_by_directory_id, task.context.directory_id, "") == root_key]
        expected_file_groups: list[tuple[list[Path], TaskData]] = []
        managed_roots: list[Path] = []
        for task in root_tasks:
            expected_groups = self._expected_download_file_groups(task)
            managed_roots.extend(self._managed_download_roots(task, expected_groups))
            if task.context.directory_id == directory.id:
                expected_file_groups.extend((group, task) for group in expected_groups)

        items: list[DirectoryIntegrityItem] = []
        for child in self._safe_iterdir(root):
            if self._is_under_any(child, managed_roots) or self._is_related_transient_download_entry(child, root_tasks, downloader_torrents):
                continue
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.unmanaged_download_entry,
                    scope=DirectoryIntegrityScope.download,
                    directory=directory,
                    path=child,
                    root=root,
                    size=self._safe_size(child) if child.is_file() else None,
                    file_created_at=self._safe_created_at(child),
                    repair_action="delete_path",
                )
            )

        for paths, task in expected_file_groups:
            if any(path.exists() for path in paths) or task.status not in DOWNLOAD_AUDIT_STATUSES:
                continue
            media_id = str(task.media_id) if task.media_id else None
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.missing_download_file,
                    scope=DirectoryIntegrityScope.download,
                    directory=directory,
                    path=paths[0],
                    root=root,
                    task_id=task.id,
                    media_id=media_id,
                    display_name=self._task_context_label(task),
                    media_display=self._media_display(media_display, media_id),
                    repair_action="refresh_task_health",
                )
            )
        return items

    def _scan_downloader_torrents(
        self,
        directory: DirectoryConfig,
        tasks: list[TaskData],
        downloader_torrents: DownloaderTorrentIndex,
        tracker_messages: TrackerMessageIndex,
        media_display: MediaDisplayIndex,
    ) -> list[DirectoryIntegrityItem]:
        root = self._resolve_existing_root(directory.download_path)
        if not root:
            return []
        items: list[DirectoryIntegrityItem] = []
        for task in tasks:
            if not self._should_scan_task_torrent(task, directory, downloader_torrents):
                continue
            torrent_hash = task.torrent_hash.lower()
            status = downloader_torrents[task.downloader_id][torrent_hash]
            task_tracker_messages = self._tracker_messages(tracker_messages, task.downloader_id, torrent_hash)
            if status.state == TorrentState.SEEDING and not task_tracker_messages:
                continue
            media_id = str(task.media_id) if task.media_id else None
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.unhealthy_downloader_torrent,
                    scope=DirectoryIntegrityScope.download,
                    directory=directory,
                    path=build_download_path(task.save_path),
                    root=root,
                    task_id=task.id,
                    media_id=media_id,
                    display_name=self._task_context_label(task),
                    media_display=self._media_display(media_display, media_id),
                    repairable=False,
                    downloader_state=status.state.value,
                    downloader_status_message=status.state.value,
                    tracker_messages=task_tracker_messages,
                    repair_action="",
                    reason="downloader_torrent_tracker_unhealthy" if task_tracker_messages else "downloader_torrent_unhealthy",
                )
            )
        items.extend(self._missing_downloader_torrent_items(directory, tasks, downloader_torrents, media_display, root))
        return items

    def _missing_downloader_torrent_items(
        self,
        directory: DirectoryConfig,
        tasks: list[TaskData],
        downloader_torrents: DownloaderTorrentIndex,
        media_display: MediaDisplayIndex,
        root: Path,
    ) -> list[DirectoryIntegrityItem]:
        items: list[DirectoryIntegrityItem] = []
        for task in tasks:
            if task.context.directory_id != directory.id or task.status not in DOWNLOAD_AUDIT_STATUSES:
                continue
            if not task.downloader_id or not task.torrent_hash or task.downloader_id not in downloader_torrents:
                continue
            if task.torrent_hash.lower() in downloader_torrents[task.downloader_id]:
                continue
            media_id = str(task.media_id) if task.media_id else None
            items.append(
                self._build_item(
                    issue_type=DirectoryIntegrityIssueType.missing_downloader_torrent,
                    scope=DirectoryIntegrityScope.download,
                    directory=directory,
                    path=build_download_path(task.save_path),
                    root=root,
                    task_id=task.id,
                    media_id=media_id,
                    display_name=self._task_context_label(task),
                    media_display=self._media_display(media_display, media_id),
                    repair_action="refresh_task_health",
                    reason="downloader_torrent_missing",
                )
            )
        return items

    @staticmethod
    def _should_scan_task_torrent(task: TaskData, directory: DirectoryConfig, downloader_torrents: DownloaderTorrentIndex) -> bool:
        if task.context.directory_id != directory.id or task.status not in DOWNLOAD_AUDIT_STATUSES:
            return False
        if not task.downloader_id or not task.torrent_hash:
            return False
        if task.downloader_id not in downloader_torrents:
            return False
        return task.torrent_hash.lower() in downloader_torrents[task.downloader_id]

    def _expected_download_file_groups(self, task: TaskData) -> list[list[Path]]:
        base = build_download_path(task.save_path)
        if not task.metadata or not task.metadata.files:
            return [[base]]
        groups: list[list[Path]] = []
        torrent_name = str(task.metadata.name or "").strip()
        for file_item in self._selected_metadata_files(task):
            if not file_item.filename:
                continue
            direct_path = base / file_item.filename
            candidates = [direct_path]
            if torrent_name and Path(file_item.filename).parts[:1] != (torrent_name,):
                candidates.append(base / torrent_name / file_item.filename)
            groups.append(candidates)
        return groups

    @staticmethod
    def _selected_metadata_files(task: TaskData) -> Iterable[TorrentFileItem]:
        if not task.metadata or not task.metadata.files:
            return []
        selected = set(task.context.selected_files or []) if task.context and task.context.selected_files else None
        for index, file_item in enumerate(task.metadata.files):
            if selected is not None and index not in selected:
                continue
            yield file_item

    def _managed_download_roots(self, task: TaskData, expected_groups: list[list[Path]]) -> list[Path]:
        base = build_download_path(task.save_path).resolve(strict=False)
        if not task.metadata or not task.metadata.files:
            return [base]
        roots: set[Path] = set()
        for expected_paths in expected_groups:
            for path in expected_paths:
                try:
                    relative = path.resolve(strict=False).relative_to(base)
                except ValueError:
                    roots.add(path.resolve(strict=False))
                    continue
                if relative.parts:
                    roots.add(base / relative.parts[0])
        return sorted(roots, key=lambda path: len(path.parts), reverse=True)

    def _is_related_transient_download_entry(self, path: Path, tasks: list[TaskData], downloader_torrents: DownloaderTorrentIndex) -> bool:
        if not self._is_transient_download_path(path):
            return False
        resolved = path.resolve(strict=False)
        for task in tasks:
            if not self._task_has_known_downloader_torrent(task, downloader_torrents):
                continue
            candidates = self._transient_download_candidates(task)
            if any(resolved == candidate.resolve(strict=False) for candidate in candidates):
                return True
        return False

    def _transient_download_candidates(self, task: TaskData) -> list[Path]:
        expected_groups = self._expected_download_file_groups(task)
        roots = self._managed_download_roots(task, expected_groups)
        candidates: set[Path] = set()
        for path in [item for group in expected_groups for item in group]:
            candidates.update(self._with_transient_suffixes(path))
        for root in roots:
            candidates.update(self._with_transient_suffixes(root))
        return sorted(candidates)

    def _build_item(
        self,
        *,
        issue_type: DirectoryIntegrityIssueType,
        scope: DirectoryIntegrityScope,
        directory: DirectoryConfig,
        path: Path,
        root: Path,
        size: int | None = None,
        file_created_at: float | None = None,
        record_created_at: float | None = None,
        task_completed_at: float | None = None,
        library_file_name: str = "",
        library_file_id: str | None = None,
        task_id: str | None = None,
        media_id: str | None = None,
        display_name: str = "",
        media_display: tuple[str, int | None] = ("", None),
        repairable: bool = True,
        downloader_state: str = "",
        downloader_status_message: str = "",
        tracker_messages: list[str] | None = None,
        repair_action: str = "",
        reason: str = "",
    ) -> DirectoryIntegrityItem:
        normalized = self._normalize_path(path)
        item_key = f"{issue_type.value}:{directory.id}:{normalized}:{library_file_id or ''}:{task_id or ''}"
        item_id = hashlib.sha1(item_key.encode("utf-8")).hexdigest()
        media_title, media_year = media_display
        return DirectoryIntegrityItem(
            id=item_id,
            issue_type=issue_type,
            scope=scope,
            directory_id=directory.id,
            directory_name=directory.name,
            display_name=display_name,
            path=normalized,
            relative_path=self._relative_to_root(path, root),
            size=size,
            file_created_at=file_created_at,
            record_created_at=record_created_at,
            task_completed_at=task_completed_at,
            library_file_name=library_file_name,
            library_file_id=library_file_id,
            task_id=task_id,
            media_id=media_id,
            media_title=media_title,
            media_year=media_year,
            downloader_state=downloader_state,
            downloader_status_message=downloader_status_message,
            tracker_messages=list(tracker_messages or []),
            repairable=repairable,
            repair_action=repair_action,
            reason=reason,
        )

    @staticmethod
    def _filter_by_policy(items: list[DirectoryIntegrityItem], issue_types: set[DirectoryIntegrityIssueType]) -> list[DirectoryIntegrityItem]:
        if not issue_types:
            return []
        return [item for item in items if item.issue_type in issue_types]

    @staticmethod
    def _media_display(media_display: MediaDisplayIndex, media_id: str | None) -> tuple[str, int | None]:
        if not media_id:
            return ("", None)
        return media_display[media_id] if media_id in media_display else ("", None)

    @staticmethod
    def _tracker_messages(tracker_messages: TrackerMessageIndex, downloader_id: str, torrent_hash: str) -> list[str]:
        key = (downloader_id, torrent_hash)
        return tracker_messages[key] if key in tracker_messages else []

    @staticmethod
    def _dict_value(items: dict[str, str], key: str, default: str) -> str:
        return items[key] if key in items else default

    @staticmethod
    def _resolve_existing_root(path: str) -> Path | None:
        value = str(path or "").strip()
        if not value:
            return None
        root = Path(value).resolve(strict=False)
        return root if root.exists() and root.is_dir() else None

    def _build_download_root_index(self, directories: list[DirectoryConfig]) -> dict[str, str]:
        roots: dict[str, str] = {}
        for directory in directories:
            root = self._resolve_existing_root(directory.download_path)
            if root:
                roots[directory.id] = self._normalize_path(root)
        return roots

    def _iter_files(self, root: Path) -> list[Path]:
        paths: list[Path] = []
        for path in root.rglob("*"):
            if self._should_skip_path(root, path):
                continue
            if path.is_file():
                paths.append(path)
        return paths

    def _safe_iterdir(self, root: Path) -> list[Path]:
        try:
            return [path for path in root.iterdir() if not self._should_skip_path(root, path)]
        except OSError as exc:
            logger.warning("Failed to inspect directory %s: %s", root, exc)
            return []

    @staticmethod
    def _should_skip_path(root: Path, path: Path) -> bool:
        if path.is_symlink():
            return True
        try:
            path.resolve(strict=False).relative_to(root.resolve(strict=False))
            return False
        except ValueError:
            return True

    @staticmethod
    def _is_transient_download_path(path: Path) -> bool:
        return any(part.lower().endswith(tuple(TRANSIENT_DOWNLOAD_SUFFIXES)) for part in path.parts)

    @staticmethod
    def _is_under_any(path: Path, roots: list[Path]) -> bool:
        resolved = path.resolve(strict=False)
        for root in roots:
            try:
                resolved.relative_to(root.resolve(strict=False))
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _task_has_known_downloader_torrent(task: TaskData, downloader_torrents: DownloaderTorrentIndex) -> bool:
        if not task.downloader_id or not task.torrent_hash:
            return False
        if task.downloader_id not in downloader_torrents:
            return False
        return task.torrent_hash.lower() in downloader_torrents[task.downloader_id]

    @staticmethod
    def _task_context_label(task: TaskData) -> str:
        resource_title = str(task.context.resource_title or "").strip() if task.context else ""
        return resource_title

    @staticmethod
    def _with_transient_suffixes(path: Path) -> set[Path]:
        return {path.with_name(f"{path.name}{suffix}") for suffix in TRANSIENT_DOWNLOAD_SUFFIXES}

    @staticmethod
    def _normalize_path(path: Path) -> str:
        return str(path.resolve(strict=False))

    @staticmethod
    def _relative_to_root(path: Path, root: Path) -> str:
        try:
            return str(path.resolve(strict=False).relative_to(root.resolve(strict=False)))
        except ValueError:
            return path.name

    @staticmethod
    def _safe_size(path: Path) -> int | None:
        try:
            return path.stat().st_size
        except OSError:
            return None

    @staticmethod
    def _safe_created_at(path: Path) -> float | None:
        try:
            return float(path.stat().st_mtime)
        except OSError:
            return None

    @staticmethod
    def _datetime_to_timestamp(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value.timestamp())
        except (AttributeError, OSError, ValueError):
            return None
