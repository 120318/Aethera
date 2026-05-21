from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from app.clients.factory import ClientFactory
from app.db.repositories.task_repository import TaskRepository
from app.schemas.domain.download import BatchJobResult, DownloadTaskCreateInput, TaskData, TaskEpisodeCoverage, TaskErrorStage, TaskStatus
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.torrent_status import TorrentStatus
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import MediaTaskSummary
from app.services.domain.library.service import library_service
from app.services.domain.download.lifecycle import DownloadCreationService
from app.services.domain.download.downloader_change import (
    TaskDownloaderChangePreview,
    TaskDownloaderChangeRequest,
    TaskDownloaderChangeService,
)
from app.services.domain.download.state import TaskStateService
from app.services.domain.download.task_runtime_service import TaskRuntimeService
from app.services.domain.download.tasks import DownloadTaskService

from . import coverage


class DownloaderDisplayInfo(BaseModel):
    name: str
    url: str | None = None


class DownloadService:
    downloader_display_info_cls = DownloaderDisplayInfo

    def __init__(self) -> None:
        self._repo = TaskRepository()
        self.client_factory = ClientFactory
        self.task_state = TaskStateService(self._repo)
        self.task_runtime = TaskRuntimeService(self._repo, self.client_factory)
        self.task_service = DownloadTaskService(
            self._repo,
            self.client_factory,
            self._get_downloader_display_map,
            self.refresh_completed_task_health,
        )
        self.coverage_service = coverage.DownloadCoverageService(self.get_tasks)
        self.creation_service = DownloadCreationService(
            self._repo,
            self.client_factory,
            self.downloader_display_info_cls,
            self.task_service,
        )
        self.downloader_change_service = TaskDownloaderChangeService(self._repo, self.client_factory)

    def _get_downloader_display_map(self) -> dict[str, DownloaderDisplayInfo]:
        return self.creation_service.get_downloader_display_map()

    def list_episode_coverage_statuses(self) -> list[TaskStatus]:
        return coverage.list_episode_coverage_statuses()

    def list_library_present_statuses(self) -> list[TaskStatus]:
        return coverage.list_library_present_statuses()

    def resolve_task_episode_coverage(self, task: TaskData) -> tuple[int | None, list[int]]:
        return coverage.resolve_task_episode_coverage(task)

    def resolve_task_episode_coverage_detail(self, task: TaskData) -> TaskEpisodeCoverage:
        return coverage.resolve_task_episode_coverage_detail(task)

    async def list_active_episodes_by_media(self, media_id: MediaID, season: int | None = None) -> set[int]:
        return await self.coverage_service.list_active_episodes_by_media(media_id, season)

    async def create_download(self, req: DownloadTaskCreateInput, search_result: ResourceSearchResult) -> TaskData:
        return await self.creation_service.create_download(req, search_result)

    async def ensure_task_download_path_consistent(self, task: TaskData) -> None:
        await self.task_service.ensure_task_download_path_consistent(task)

    async def get_tasks(
        self,
        status: list[TaskStatus] | None = None,
        media_id: MediaID | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskData]:
        return await self.task_service.get_tasks(
            status=status,
            media_id=media_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

    async def list_media_tasks_for_overview(self, *, status: list[TaskStatus] | None = None, media_id: MediaID | None = None) -> list[TaskData]:
        return await self.task_service.list_media_tasks_for_overview(status=status, media_id=media_id)

    async def get_tasks_by_statuses(self, statuses: list[TaskStatus], limit: int | None = None, offset: int = 0) -> list[TaskData]:
        return await self.task_service.get_tasks_by_statuses(statuses, limit=limit, offset=offset)

    async def get_tasks_by_ids(self, task_ids: list[str]) -> Mapping[str, TaskData]:
        return await self.task_service.get_tasks_by_ids(task_ids)

    async def summarize_media_tasks_by_media_ids(self, media_ids: list[MediaID]) -> Mapping[str, MediaTaskSummary]:
        return await self.task_service.summarize_media_tasks_by_media_ids(media_ids)

    async def find_task_by_id(self, task_id: str) -> TaskData | None:
        return await self.task_service.find_task_by_id(task_id)

    async def pause_tasks(self, task_ids: list[str]) -> Mapping[str, bool]:
        return await self.task_service.pause_tasks(task_ids)

    async def pause_task(self, task_id: str) -> bool:
        return await self.task_service.pause_task(task_id)

    async def resume_tasks(self, task_ids: list[str]) -> Mapping[str, bool]:
        return await self.task_service.resume_tasks(task_ids)

    async def resume_task(self, task_id: str) -> bool:
        return await self.task_service.resume_task(task_id)

    async def delete_task_with_cleanup(self, task_id: str, *, delete_files: bool = False, force: bool = False, delete_library_files: bool = False) -> tuple[int, bool]:
        return await self.task_service.delete_task_with_cleanup(
            task_id,
            delete_files=delete_files,
            force=force,
            delete_library_files=delete_library_files,
        )

    async def delete_task(self, task_id: str, delete_files: bool = False, force_delete_record: bool = False) -> bool:
        return await self.task_service.delete_task(task_id, delete_files=delete_files, force_delete_record=force_delete_record)

    async def preview_task_downloader_change(
        self,
        task_id: str,
        request: TaskDownloaderChangeRequest,
    ) -> TaskDownloaderChangePreview:
        return await self.downloader_change_service.preview(task_id, request)

    async def change_task_downloader(
        self,
        task_id: str,
        request: TaskDownloaderChangeRequest,
    ) -> TaskDownloaderChangePreview:
        return await self.downloader_change_service.execute(task_id, request)

    async def finalize_task_downloader_changes(self, limit: int = 100) -> int:
        return await self.downloader_change_service.finalize_active_migrations(limit=limit)

    async def get_torrent_status_by_task_ids(self, task_ids: list[str]) -> Mapping[str, TorrentStatus]:
        return await self.task_service.get_torrent_status_by_task_ids(task_ids)

    async def update_task_state(
        self,
        task_id: str,
        new_status: TaskStatus,
        error_key: str | None = None,
        progress: float | None = None,
        error_stage: TaskErrorStage | None = None,
        error_params: dict[str, str] | None = None,
    ) -> bool:
        return await self.task_state.update_task_state(
            task_id,
            new_status,
            error_key=error_key,
            progress=progress,
            error_stage=error_stage,
            error_params=error_params,
        )

    async def sync_active_downloads(self) -> BatchJobResult:
        finalized = await self.finalize_task_downloader_changes()
        result = await self.task_runtime.sync_active_downloads(self.get_tasks_by_statuses, self.update_task_state)
        return result.model_copy(
            update={
                "processed": result.processed + finalized,
                "updated": result.updated + finalized,
            }
        )

    async def sync_active_task(self, task_id: str) -> bool:
        return await self.task_runtime.sync_active_task(task_id, self.find_task_by_id, self.update_task_state)

    async def recover_stuck_transferring_tasks(self, force: bool = False, timeout_seconds: int = 1800) -> int:
        return await self.task_runtime.recover_stuck_transferring_tasks(
            self.get_tasks,
            self.update_task_state,
            force=force,
            timeout_seconds=timeout_seconds,
        )

    def _is_valid_state_transition(self, current: str, new: TaskStatus) -> bool:
        return self.task_state.is_valid_state_transition(current, new)

    async def refresh_completed_task_health(self, task_id: str, expected_total_count: int | None = None) -> bool:
        return await self.task_runtime.refresh_completed_task_health(
            task_id,
            self.update_task_state,
            library_service.reconcile_task_primary_files,
            expected_total_count=expected_total_count,
        )


download_service = DownloadService()
