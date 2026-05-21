from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Awaitable, Callable, Protocol

from app.schemas.constants.event_types import EventTypes
from app.schemas.exception.exceptions import DownloadException
from app.schemas.domain.download import BatchJobResult, TaskData, TaskErrorStage, TaskFieldPatch, TaskStatus
from app.schemas.domain.event import EventActor, EventEntityRef, EventSource, MediaEventCreate
from app.schemas.domain.addon_events import DownloadTaskEventMeta
from app.schemas.domain.library import LibraryTaskFileHealth
from app.schemas.domain.torrent_status import TorrentStatus
from app.services.audit.event_service import event_service
from app.services.platform.domain_lock_service import domain_lock_service

logger = logging.getLogger("app.services.download")


class TaskRuntimeRepository(Protocol):
    async def find_by_id(self, task_id: str) -> TaskData | None: ...

    async def update_fields(self, fields: TaskFieldPatch, cond: str) -> bool: ...

    def cond_id(self, task_id: str) -> str: ...


class TaskRuntimeDownloadClient(Protocol):
    async def get_torrents(self, hashes: list[str]) -> list[TorrentStatus]: ...

    async def get_torrent_info(self, torrent_hash: str) -> TorrentStatus | None: ...


class TaskRuntimeDownloadClientFactory(Protocol):
    def get_download_client(self, downloader_id: str | None = None) -> TaskRuntimeDownloadClient: ...


class TaskRuntimeService:
    def __init__(
        self,
        repo: TaskRuntimeRepository,
        client_factory: TaskRuntimeDownloadClientFactory,
    ) -> None:
        self._repo = repo
        self._client_factory = client_factory

    async def sync_active_downloads(
        self,
        get_tasks_by_statuses: Callable[[list[TaskStatus]], Awaitable[list[TaskData]]],
        update_task_state: Callable[[str, TaskStatus, str | None, float | None, TaskErrorStage | None], Awaitable[bool]],
    ) -> BatchJobResult:
        active_statuses = [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED]
        active_tasks = await get_tasks_by_statuses(active_statuses)
        active_tasks = [task for task in active_tasks if not await domain_lock_service.is_task_op_locked(task.id)]
        if not active_tasks:
            return BatchJobResult(processed=0, updated=0)

        tasks_by_downloader: dict[str, list[TaskData]] = {}
        for task in active_tasks:
            if task.downloader_id:
                tasks_by_downloader.setdefault(task.downloader_id, []).append(task)

        updated_count = 0
        for downloader_id, tasks in tasks_by_downloader.items():
            try:
                client = self._client_factory.get_download_client(downloader_id)
                statuses = await client.get_torrents(hashes=[task.torrent_hash for task in tasks])
            except (DownloadException, RuntimeError, ValueError) as exc:
                logger.error("Failed to sync active downloads for downloader %s: %s", downloader_id, exc)
                continue
            status_map = {torrent.hash.lower(): torrent for torrent in statuses}

            for task in tasks:
                torrent_hash = task.torrent_hash.lower()
                torrent_status = status_map[torrent_hash] if torrent_hash in status_map else None
                if await self._process_active_task_state(
                    task,
                    torrent_status,
                    update_task_state,
                ):
                    updated_count += 1

        return BatchJobResult(processed=len(active_tasks), updated=updated_count)

    async def sync_active_task(
        self,
        task_id: str,
        find_task_by_id: Callable[[str], Awaitable[TaskData | None]],
        update_task_state: Callable[[str, TaskStatus, str | None, float | None, TaskErrorStage | None], Awaitable[bool]],
    ) -> bool:
        task = await find_task_by_id(task_id)
        if not task or task.status not in [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED]:
            return False
        if not task.downloader_id or not task.torrent_hash:
            return False

        try:
            client = self._client_factory.get_download_client(task.downloader_id)
            torrent_status = await client.get_torrent_info(task.torrent_hash)
        except (DownloadException, RuntimeError, ValueError) as exc:
            logger.warning("Failed to sync active task %s: %s", task.id, exc)
            return False

        return await self._process_active_task_state(task, torrent_status, update_task_state)

    async def recover_stuck_transferring_tasks(
        self,
        get_tasks: Callable[..., Awaitable[list[TaskData]]],
        update_task_state: Callable[[str, TaskStatus, str | None, float | None, TaskErrorStage | None], Awaitable[bool]],
        force: bool = False,
        timeout_seconds: int = 1800,
    ) -> int:
        stuck_tasks = await get_tasks(status=[TaskStatus.TRANSFERRING])
        if not stuck_tasks:
            return 0

        count = 0
        now = datetime.now()
        for task in stuck_tasks:
            should_reset = force
            if not should_reset and task.updated_at:
                updated_at = task.updated_at
                if (now - updated_at).total_seconds() > timeout_seconds:
                    should_reset = True

            if should_reset or not task.updated_at:
                if await update_task_state(
                    task.id,
                    TaskStatus.FINISHED,
                    None,
                    None,
                    None,
                ):
                    count += 1
        return count

    async def refresh_completed_task_health(
        self,
        task_id: str,
        update_task_state: Callable[[str, TaskStatus, str | None, float | None, TaskErrorStage | None], Awaitable[bool]],
        resolve_library_health: Callable[[TaskData, int | None], Awaitable[LibraryTaskFileHealth]],
        expected_total_count: int | None = None,
    ) -> bool:
        task = await self._repo.find_by_id(task_id)
        if not task:
            return False
        if task.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL_MISSING,
            TaskStatus.SEEDING_ABSENT,
            TaskStatus.FILE_MISSING,
        ]:
            return False

        has_torrent: bool | None = False
        if task.downloader_id and task.torrent_hash:
            try:
                client = self._client_factory.get_download_client(task.downloader_id)
                torrent_info = await client.get_torrent_info(task.torrent_hash)
                has_torrent = torrent_info is not None
            except (DownloadException, RuntimeError, ValueError) as exc:
                logger.warning("Failed to inspect torrent health for task %s: %s", task.id, exc)
                has_torrent = None

        target_status = await self._resolve_library_audit_status(
            task,
            has_torrent,
            resolve_library_health,
            expected_total_count,
        )
        if target_status is None or target_status == task.status:
            return False
        return await update_task_state(task.id, target_status, None, None, None)

    async def _process_active_task_state(
        self,
        task: TaskData,
        torrent_status: TorrentStatus | None,
        update_task_state: Callable[[str, TaskStatus, str | None, float | None, TaskErrorStage | None], Awaitable[bool]],
    ) -> bool:
        if task.status == TaskStatus.VOID:
            return False
        if torrent_status:
            progress = torrent_status.progress
            if progress is not None and progress >= 0.999 and task.status in [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED]:
                event_service.emit_media(
                    MediaEventCreate(
                        type=EventTypes.DOWNLOAD_COMPLETED,
                        message_params={"downloader_id": task.downloader_id or ""},
                        media=task.context.media,
                        task_id=task.id,
                        actor=EventActor.system,
                        source=EventSource.base,
                        entities=[
                            EventEntityRef(type="task", id=task.id),
                            EventEntityRef(type="media", id=str(task.media_id)),
                        ],
                    ),
                    meta=DownloadTaskEventMeta(
                        task_id=task.id,
                        media_id=task.media_id,
                        status=task.status,
                        downloader_id=task.downloader_id,
                        resource_title=task.context.resource_title,
                        torrent_name=task.metadata.name if task.metadata else None,
                        torrent_hash=task.torrent_hash,
                        progress=task.progress,
                        selected_files=list(task.context.selected_files or []),
                        total_files=len(task.metadata.files) if task.metadata and task.metadata.files else None,
                    ),
                )
                return await update_task_state(task.id, TaskStatus.FINISHED, None, 1.0, None)
            if progress is not None and progress < 1.0 and task.status == TaskStatus.PENDING:
                return await update_task_state(task.id, TaskStatus.DOWNLOADING, None, progress, None)
            if progress is not None and abs(task.progress - progress) > 0.005:
                await self._repo.update_fields(
                    TaskFieldPatch(progress=progress, updated_at=datetime.now()),
                    self._repo.cond_id(task.id),
                )
                return True
        else:
            if task.status in [TaskStatus.PENDING, TaskStatus.DOWNLOADING]:
                return await update_task_state(task.id, TaskStatus.VOID, None, None, None)
            if task.status in [TaskStatus.FINISHED, TaskStatus.TRANSFERRING, TaskStatus.COMPLETED]:
                return await update_task_state(task.id, TaskStatus.SEEDING_ABSENT, None, None, None)
        return False

    async def _resolve_library_audit_status(
        self,
        task: TaskData,
        has_torrent: bool | None,
        resolve_library_health: Callable[[TaskData, int | None], Awaitable[LibraryTaskFileHealth]],
        expected_total_count: int | None = None,
    ) -> TaskStatus | None:
        health = await resolve_library_health(task, expected_total_count)
        existing_count = health.existing_primary_count
        total_count = health.total_primary_count

        if total_count == 0 or existing_count == 0:
            return TaskStatus.FILE_MISSING
        if existing_count < total_count:
            return TaskStatus.PARTIAL_MISSING
        if has_torrent is True:
            return TaskStatus.COMPLETED
        if has_torrent is False:
            return TaskStatus.SEEDING_ABSENT
        return None
