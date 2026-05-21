from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import qbittorrentapi

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.alert import AlertResolveRequest
from app.schemas.domain.torrent_status import TorrentStatus
from app.schemas.exception.exceptions import DownloadException
from app.services.domain.alerts import alert_service
from app.services.domain.directory import directory_service
from app.services.domain.download.downloader_delete import delete_downloader_task
from app.services.domain.library.service import library_service
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.library_paths import build_download_path

if TYPE_CHECKING:
    from app.schemas.media_id import MediaID
    from app.schemas.runtime.media_management import MediaTaskSummary
    from app.services.integration.download.client import DownloadClient


class DownloaderDisplayInfoView(Protocol):
    name: str
    url: str | None


class DownloadTaskService:
    def __init__(
        self,
        repo,
        client_factory,
        downloader_display_map_provider: Callable[[], Mapping[str, DownloaderDisplayInfoView]],
        refresh_completed_task_health: Callable[[str, int | None], Awaitable[bool]],
    ) -> None:
        self._repo = repo
        self._client_factory = client_factory
        self._get_downloader_display_map = downloader_display_map_provider
        self._refresh_completed_task_health = refresh_completed_task_health

    @staticmethod
    def normalize_status_values(statuses: list[TaskStatus] | None) -> list[str] | None:
        if statuses is None:
            return None
        return [item.value for item in statuses]

    def resolve_task_client(self, task: TaskData) -> DownloadClient | None:
        if task.downloader_id:
            return self._client_factory.get_download_client(task.downloader_id)
        directory_id = task.context.directory_id if task.context else None
        if not directory_id:
            return None
        binding = directory_service.get_download_binding(directory_id)
        if not binding or not binding.downloader_id:
            return None
        return self._client_factory.get_download_client(binding.downloader_id)

    @staticmethod
    async def has_live_torrent(task: TaskData, client: DownloadClient | None) -> bool:
        if not client or not task.torrent_hash:
            return False
        info = await client.get_torrent_info(task.torrent_hash)
        return info is not None

    @staticmethod
    def normalize_download_path(path) -> Path | None:
        if path is None:
            return None
        value = str(path).strip()
        if not value:
            return None
        return build_download_path(value).resolve(strict=False)

    async def ensure_live_torrent_download_path_matches_hash(
        self,
        client: DownloadClient | None,
        torrent_hash: str | None,
        expected_download_path,
    ) -> None:
        if not client or not torrent_hash:
            return
        info = await client.get_torrent_info(torrent_hash)
        if not info:
            return
        expected_path = self.normalize_download_path(expected_download_path)
        actual_path = self.normalize_download_path(info.save_path)
        if expected_path is None or actual_path is None:
            return
        if expected_path != actual_path:
            from app.schemas.exception.exceptions import DownloadTorrentPathConflictException

            raise DownloadTorrentPathConflictException(params={"expected": str(expected_path), "actual": str(actual_path)})

    async def ensure_task_download_path_consistent(self, task: TaskData) -> None:
        expected_path = self.normalize_download_path(task.save_path)
        if expected_path is None:
            return
        client = self.resolve_task_client(task)
        await self.ensure_live_torrent_download_path_matches_hash(client, task.torrent_hash, expected_path)

    async def has_cached_live_torrent(
        self,
        task: TaskData,
        client: DownloadClient | None,
        cache: MutableMapping[tuple[str, str], bool],
    ) -> bool:
        if not client or not task.torrent_hash:
            return False
        downloader_id = task.downloader_id
        if not downloader_id:
            return await self.has_live_torrent(task, client)
        cache_key = (downloader_id, task.torrent_hash.lower())
        if cache_key in cache:
            return cache[cache_key]
        present = await self.has_live_torrent(task, client)
        cache[cache_key] = present
        return present

    async def get_tasks(
        self,
        *,
        status: list[TaskStatus] | None = None,
        media_id: MediaID | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskData]:
        tasks = await self._repo.find_with_filters(
            status=self.normalize_status_values(status),
            media_id=media_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        return self.enrich_tasks_with_downloader_info(tasks)

    async def list_media_tasks_for_overview(
        self,
        *,
        status: list[TaskStatus] | None = None,
        media_id: MediaID | None = None,
    ) -> list[TaskData]:
        return await self._repo.find_with_filters(
            status=self.normalize_status_values(status),
            media_id=media_id,
        )

    async def get_tasks_by_statuses(
        self,
        statuses: list[TaskStatus],
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskData]:
        tasks = await self._repo.find_by_statuses(statuses, limit=limit, offset=offset)
        return self.enrich_tasks_with_downloader_info(tasks)

    async def get_tasks_by_ids(self, task_ids: list[str]) -> Mapping[str, TaskData]:
        if not task_ids:
            return {}
        tasks = await self._repo.find_by_ids(task_ids)
        enriched = self.enrich_tasks_with_downloader_info(tasks)
        return {t.id: t for t in enriched}

    async def summarize_media_tasks_by_media_ids(self, media_ids: list[MediaID]) -> Mapping[str, MediaTaskSummary]:
        return await self._repo.summarize_by_media_ids(media_ids)

    async def find_task_by_id(self, task_id: str) -> TaskData | None:
        task = await self._repo.find_by_id(task_id)
        if not task:
            return None
        enriched = self.enrich_tasks_with_downloader_info([task])
        return enriched[0] if enriched else None

    def enrich_tasks_with_downloader_info(self, tasks: list[TaskData]) -> list[TaskData]:
        downloader_map = self._get_downloader_display_map()
        for task in tasks:
            if task.downloader_id and task.downloader_id in downloader_map:
                display = downloader_map[task.downloader_id]
                task.download_client = display.name
                task.download_client_url = display.url
        return tasks

    async def pause_tasks(self, task_ids: list[str]) -> Mapping[str, bool]:
        return {task_id: await self.pause_task(task_id) for task_id in task_ids} if task_ids else {}

    async def pause_task(self, task_id: str) -> bool:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            task = await self.find_task_by_id(task_id)
            if not task or not task.downloader_id:
                return False
            if task.status == TaskStatus.MIGRATING:
                raise DownloadException("backendErrors.taskBusy")
            client = self._client_factory.get_download_client(task.downloader_id)
            return await client.pause_torrents([task.torrent_hash])

    async def resume_tasks(self, task_ids: list[str]) -> Mapping[str, bool]:
        return {task_id: await self.resume_task(task_id) for task_id in task_ids} if task_ids else {}

    async def resume_task(self, task_id: str) -> bool:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            task = await self.find_task_by_id(task_id)
            if not task or not task.downloader_id:
                return False
            if task.status == TaskStatus.MIGRATING:
                raise DownloadException("backendErrors.taskBusy")
            client = self._client_factory.get_download_client(task.downloader_id)
            return await client.start_torrents([task.torrent_hash])

    async def delete_task_with_cleanup(
        self,
        task_id: str,
        *,
        delete_files: bool = False,
        force: bool = False,
        delete_library_files: bool = False,
    ) -> tuple[int, bool]:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")

            deleted_library_files_count = 0
            expected_total_count = 0
            if delete_library_files:
                expected_total_count = await library_service.count_task_primary_files(task_id)
                deleted_library_files_count = await library_service.delete_task_library_files(task_id=task_id, force=force)
                if expected_total_count > 0:
                    await self._refresh_completed_task_health(task_id, expected_total_count)

            deleted_task = await self.delete_task_unlocked(
                task_id,
                delete_files=delete_files,
                force_delete_record=force,
            )
            return deleted_library_files_count, deleted_task

    async def delete_task(
        self,
        task_id: str,
        delete_files: bool = False,
        force_delete_record: bool = False,
    ) -> bool:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            return await self.delete_task_unlocked(
                task_id,
                delete_files=delete_files,
                force_delete_record=force_delete_record,
            )

    async def delete_task_unlocked(
        self,
        task_id: str,
        *,
        delete_files: bool = False,
        force_delete_record: bool = False,
    ) -> bool:
        task = await self._repo.find_by_id(task_id)
        if not task:
            return False
        if task.status == TaskStatus.MIGRATING:
            raise DownloadException("backendErrors.taskBusy")
        if task.downloader_id:
            client = self._client_factory.get_download_client(task.downloader_id)
            try:
                await delete_downloader_task(client, task, delete_files=delete_files)
            except (DownloadException, RuntimeError, ValueError):
                if not force_delete_record:
                    raise
        await self._repo.delete_by_id(task.id)
        alert_service.resolve_alert(AlertResolveRequest(fingerprint=f"task.transfer:{task.id}"))
        return True

    async def get_torrent_status_by_task_ids(self, task_ids: list[str]) -> Mapping[str, TorrentStatus]:
        if not task_ids:
            return {}
        task_map = await self.get_tasks_by_ids(task_ids)
        downloader_hashes: dict[str, list[str]] = {}
        for task in task_map.values():
            if task.downloader_id and task.torrent_hash:
                downloader_hashes.setdefault(task.downloader_id, []).append(task.torrent_hash)

        result: dict[str, TorrentStatus] = {}
        for did, hashes in downloader_hashes.items():
            try:
                client = self._client_factory.get_download_client(did)
                statuses = await client.get_torrents(hashes=sorted({item.lower() for item in hashes}))
            except (DownloadException, qbittorrentapi.APIError, RuntimeError, ValueError):
                continue
            for status in statuses:
                for task_id, task in task_map.items():
                    if task.downloader_id == did and task.torrent_hash.lower() == status.hash.lower():
                        result[task_id] = status
        return result
