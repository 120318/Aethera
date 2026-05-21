from __future__ import annotations

import asyncio
import time
import uuid

from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityDirectorySummary,
    DirectoryIntegrityItem,
    DirectoryIntegrityRepairRequest,
    DirectoryIntegrityRepairResult,
    DirectoryIntegrityResult,
)
from app.services.application.workflows.directory_integrity.latest_store import LATEST_RESULT_PATH, DirectoryIntegrityLatestStore
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.directory_integrity.models import DirectorySizeIndex
from app.services.domain.directory_integrity.repair import DirectoryIntegrityRepairExecutor
from app.services.domain.directory_integrity.scanner import DirectoryIntegrityScanner
from app.services.domain.directory_integrity.size_summary import build_directory_size_index
from app.services.domain.directory_integrity.snapshot import DirectoryIntegritySnapshotLoader
from app.services.domain.directory_integrity.summary import build_directory_integrity_count_summary
from app.services.domain.transfer import transfer_service
from app.services.integration.torrent.directory_integrity import DirectoryIntegrityTorrentSnapshot


class DirectoryIntegrityService:
    def __init__(self) -> None:
        self.latest_store = DirectoryIntegrityLatestStore()
        self.snapshot_loader = DirectoryIntegritySnapshotLoader()
        self.torrent_snapshot = DirectoryIntegrityTorrentSnapshot()
        self.scanner = DirectoryIntegrityScanner()
        self.repair_executor = DirectoryIntegrityRepairExecutor()
        self._scan_lock = asyncio.Lock()

    async def latest(self) -> DirectoryIntegrityResult | None:
        self.latest_store.path = LATEST_RESULT_PATH
        return await self.latest_store.load()

    async def scan(self, directory_id: str | None = None) -> DirectoryIntegrityResult:
        async with self._scan_lock:
            return await self._scan_once(directory_id)

    async def _scan_once(self, directory_id: str | None = None) -> DirectoryIntegrityResult:
        self.latest_store.path = LATEST_RESULT_PATH
        self.snapshot_loader.settings_service = settings_service
        snapshot = await self.snapshot_loader.load(directory_id)
        downloader_torrents = await self.torrent_snapshot.load_torrents(snapshot.tasks)
        tracker_messages = await self.torrent_snapshot.load_tracker_messages(downloader_torrents)
        scan_snapshot = snapshot.__class__(
            directories=snapshot.directories,
            all_directories=snapshot.all_directories,
            policies=snapshot.policies,
            library_files=snapshot.library_files,
            tasks=snapshot.tasks,
            media_display=snapshot.media_display,
            downloader_torrents=downloader_torrents,
            tracker_messages=tracker_messages,
        )
        result = self.scanner.scan(scan_snapshot, scan_id=str(uuid.uuid4()), scanned_at=time.time())
        if directory_id:
            previous = await self.latest()
            if previous:
                size_index = build_directory_size_index(snapshot.all_directories, snapshot.tasks, snapshot.all_directories)
                active_directory_ids = {directory.id for directory in snapshot.all_directories}
                result = self._merge_directory_scan_result(previous, result, directory_id, size_index, active_directory_ids)
        await self.latest_store.save(result)
        return result

    async def repair(self, request: DirectoryIntegrityRepairRequest) -> DirectoryIntegrityRepairResult:
        self.repair_executor.download_service = download_service
        self.repair_executor.transfer_service = transfer_service
        latest = await self.latest()
        if not latest or latest.scan_id != request.scan_id:
            latest = await self.scan()
        items = self._selected_repairable_items(latest.items, request.item_ids)
        result = await self.repair_executor.repair(items)
        await self.scan()
        return result

    @staticmethod
    def _selected_repairable_items(items: list[DirectoryIntegrityItem], item_ids: list[str]) -> list[DirectoryIntegrityItem]:
        selected = set(item_ids)
        return [item for item in items if item.repairable and (not selected or item.id in selected)]

    @staticmethod
    def _merge_directory_scan_result(
        previous: DirectoryIntegrityResult,
        current: DirectoryIntegrityResult,
        directory_id: str,
        size_index: DirectorySizeIndex,
        active_directory_ids: set[str],
    ) -> DirectoryIntegrityResult:
        items = [item for item in previous.items if item.directory_id in active_directory_ids and item.directory_id != directory_id]
        items.extend(item for item in current.items if item.directory_id == directory_id)
        directories = []
        current_directories = {item.directory_id: item for item in current.summary.directories}
        replaced = False
        for directory in previous.summary.directories:
            if directory.directory_id not in active_directory_ids:
                continue
            if directory.directory_id == directory_id:
                if directory_id in current_directories:
                    directories.append(DirectoryIntegrityService._with_directory_size(current_directories[directory_id], size_index))
                replaced = True
                continue
            directories.append(DirectoryIntegrityService._with_directory_size(directory, size_index))
        if not replaced and directory_id in current_directories:
            directories.append(DirectoryIntegrityService._with_directory_size(current_directories[directory_id], size_index))
        counts = build_directory_integrity_count_summary(items)
        global_sizes = size_index.global_summary
        summary = previous.summary.model_copy(
            update={
                **counts.model_dump(),
                "physical_size": global_sizes.physical_size,
                "logical_size": global_sizes.logical_size,
                "library_logical_size": global_sizes.library_logical_size,
                "download_logical_size": global_sizes.download_logical_size,
                "directories": directories,
            }
        )
        return current.model_copy(update={"items": items, "summary": summary})

    @staticmethod
    def _with_directory_size(
        directory: DirectoryIntegrityDirectorySummary,
        size_index: DirectorySizeIndex,
    ) -> DirectoryIntegrityDirectorySummary:
        if directory.directory_id not in size_index.directories:
            return directory
        size = size_index.directories[directory.directory_id]
        return directory.model_copy(
            update={
                "physical_size": size.physical_size,
                "logical_size": size.logical_size,
                "library_logical_size": size.library_logical_size,
                "download_logical_size": size.download_logical_size,
            }
        )

    @property
    def library_repo(self):
        return self.snapshot_loader.library_repo

    @library_repo.setter
    def library_repo(self, value) -> None:
        self.snapshot_loader.library_repo = value
        self.repair_executor.library_repo = value

    @property
    def task_repo(self):
        return self.snapshot_loader.task_repo

    @task_repo.setter
    def task_repo(self, value) -> None:
        self.snapshot_loader.task_repo = value

    @property
    def profile_repo(self):
        return self.snapshot_loader.profile_repo

    @profile_repo.setter
    def profile_repo(self, value) -> None:
        self.snapshot_loader.profile_repo = value

    @property
    def episode_repo(self):
        return self.repair_executor.episode_repo

    @episode_repo.setter
    def episode_repo(self, value) -> None:
        self.repair_executor.episode_repo = value

    @property
    def artifact_repo(self):
        return self.repair_executor.artifact_repo

    @artifact_repo.setter
    def artifact_repo(self, value) -> None:
        self.repair_executor.artifact_repo = value

    @property
    def client_factory(self):
        return self.torrent_snapshot.client_factory

    @client_factory.setter
    def client_factory(self, value) -> None:
        self.torrent_snapshot.client_factory = value


directory_integrity_service = DirectoryIntegrityService()
