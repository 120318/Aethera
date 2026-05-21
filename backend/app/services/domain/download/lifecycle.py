from __future__ import annotations

import logging
import uuid
from datetime import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from app.schemas.config import DownloaderConfig
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import DownloadTaskEventMeta
from app.schemas.domain.download import DownloadTaskCreateInput, TaskContext, TaskData, TaskStatus
from app.schemas.domain.event import EventActor, EventEntityRef, EventSource, MediaEventCreate
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.exception import ConfigurationException
from app.schemas.exception.exceptions import DownloadException, DownloadTaskAlreadyExistsException, InvalidRequestException
from app.services.audit.event_service import event_service
from app.services.domain.directory import directory_service
from app.services.config.settings_service import settings_service
from app.services.domain.resource.parser import resource_parser
from app.services.domain.resource.torrent_metadata import build_torrent_payload
from app.services.integration.torrent import torrent_service
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.library_paths import to_download_relative_path

if TYPE_CHECKING:
    from app.services.integration.download.client import DownloadClient


logger = logging.getLogger("app.services.download")


class DownloaderDisplayInfoView(Protocol):
    name: str
    url: str | None


class DownloadCreationService:
    def __init__(self, repo, client_factory, downloader_display_info_cls, task_service) -> None:
        self._repo = repo
        self._client_factory = client_factory
        self._downloader_display_info_cls = downloader_display_info_cls
        self._task_service = task_service

    def get_enabled_downloaders(self) -> list[DownloaderConfig]:
        return settings_service.list_downloaders(enabled_only=True)

    def get_downloader_display_map(self) -> Mapping[str, DownloaderDisplayInfoView]:
        downloader_map = {}
        for downloader in self.get_enabled_downloaders():
            if not downloader.id:
                continue
            downloader_map[downloader.id] = self._downloader_display_info_cls(
                name=downloader.name or downloader.type or downloader.id,
                url=downloader.url,
            )
        return downloader_map

    @staticmethod
    def resolve_download_target(directory_id: str):
        try:
            return directory_service.resolve_download_target(directory_id)
        except ConfigurationException as exc:
            raise DownloadException(
                "backendErrors.downloadTaskCreateFailed",
                params={"reason_key": exc.message_key, "reason_params": exc.params},
            ) from exc

    @staticmethod
    def build_task_context(req: DownloadTaskCreateInput, search_result, parsed_attributes=None) -> TaskContext:
        return TaskContext(
            indexer=search_result.indexer_name or search_result.indexer_id or search_result.site,
            download_url=search_result.download_url,
            page_url=search_result.detail_url or search_result.torrent_url,
            resource_title=search_result.title,
            media=req.media,
            parsed_attributes=parsed_attributes or resource_parser.parse(search_result.title, desc=search_result.description),
            directory_id=req.directory_id,
            selected_files=req.selected_files or [],
            search_result=search_result,
        )

    @staticmethod
    def build_file_priorities(
        selected_files: list[int] | None,
        files: list[TorrentFileItem] | None,
    ) -> list[int] | None:
        if not selected_files or not files:
            return None
        num_files = len(files)
        file_priorities = [0] * num_files
        for idx in selected_files:
            if 0 <= idx < num_files:
                file_priorities[idx] = 1
        return file_priorities

    @staticmethod
    def _expand_selected_files(
        requested_files: list[int] | None,
        files: list[TorrentFileItem] | None,
    ) -> set[int]:
        if not files:
            return set()
        num_files = len(files)
        if not requested_files:
            return set(range(num_files))
        return {idx for idx in requested_files if 0 <= idx < num_files}

    @staticmethod
    def _task_selected_files(task: TaskData, files: list[TorrentFileItem] | None) -> set[int]:
        if not task.context:
            return set()
        return DownloadCreationService._expand_selected_files(task.context.selected_files, files)

    @staticmethod
    def _selection_union(tasks: list[TaskData], files: list[TorrentFileItem] | None) -> list[int]:
        selected: set[int] = set()
        for task in tasks:
            selected.update(DownloadCreationService._task_selected_files(task, files))
        return sorted(selected)

    @staticmethod
    def _task_status_after_selection_expansion(status: TaskStatus) -> TaskStatus:
        if status in {
            TaskStatus.FINISHED,
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL_MISSING,
            TaskStatus.SEEDING_ABSENT,
            TaskStatus.FILE_MISSING,
        }:
            return TaskStatus.DOWNLOADING
        return status

    async def _expand_existing_task_selection(
        self,
        *,
        task: TaskData,
        hash_tasks: list[TaskData],
        requested_files: list[int] | None,
        client: DownloadClient,
    ) -> TaskData:
        files = task.metadata.files if task.metadata else []
        requested = self._expand_selected_files(requested_files, files)
        existing = self._task_selected_files(task, files)
        if not requested or requested.issubset(existing):
            logger.info(
                "Download request blocked by existing task: media=%s task=%s hash=%s",
                task.media_id,
                task.id,
                task.torrent_hash,
            )
            raise DownloadTaskAlreadyExistsException()

        merged = sorted(existing | requested)
        task.context.selected_files = merged
        task.status = self._task_status_after_selection_expansion(task.status)
        task.updated_at = datetime.now()
        await self._repo.update_task(task)
        await self.sync_existing_torrent_selection(
            client,
            task.torrent_hash,
            self._selection_union(hash_tasks, files),
            files,
        )
        logger.info(
            "Expanded existing download task selection: media=%s task=%s hash=%s selected_files=%d",
            task.media_id,
            task.id,
            task.torrent_hash,
            len(merged),
        )
        self.emit_download_started(task, task.context.media)
        return task

    @staticmethod
    def _existing_task_matches_download_context(
        *,
        task: TaskData,
        req: DownloadTaskCreateInput,
        download_path: str,
    ) -> bool:
        task_media = task.context.media if task.context else None
        if task_media is None:
            return False
        if task_media.media_id != req.media.media_id:
            return False
        if task_media.season_number != req.media.season_number:
            return False
        if task.context.directory_id != req.directory_id:
            return False
        expected_save_path = to_download_relative_path(download_path)
        if task.save_path and task.save_path != expected_save_path:
            return False
        return True

    @staticmethod
    def _existing_task_matches_torrent_reuse_context(
        *,
        task: TaskData,
        req: DownloadTaskCreateInput,
        download_path: str,
    ) -> bool:
        task_media = task.context.media if task.context else None
        if task_media is None:
            return False
        if task_media.media_id != req.media.media_id:
            return False
        if task.context.directory_id != req.directory_id:
            return False
        expected_save_path = to_download_relative_path(download_path)
        if task.save_path and task.save_path != expected_save_path:
            return False
        return True

    def _find_existing_task_for_context(
        self,
        *,
        tasks: list[TaskData],
        req: DownloadTaskCreateInput,
        download_path: str,
    ) -> TaskData | None:
        for task in tasks:
            if self._existing_task_matches_download_context(task=task, req=req, download_path=download_path):
                return task
        return None

    def _torrent_reuse_context_is_consistent(
        self,
        *,
        tasks: list[TaskData],
        req: DownloadTaskCreateInput,
        download_path: str,
    ) -> bool:
        for task in tasks:
            if not self._existing_task_matches_torrent_reuse_context(task=task, req=req, download_path=download_path):
                return False
        return True

    @staticmethod
    def resolve_download_tags() -> list[str] | None:
        tag = settings_service.get_base_system_config().download.default_tag.strip()
        return [tag] if tag else None

    def emit_download_started(self, task: TaskData, media) -> None:
        downloader_name = None
        if task.downloader_id:
            display_map = self.get_downloader_display_map()
            downloader_info = (
                display_map[task.downloader_id]
                if task.downloader_id in display_map
                else self._downloader_display_info_cls(name=task.downloader_id)
            )
            downloader_name = downloader_info.name
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.DOWNLOAD_STARTED,
                message_params={"downloader_id": downloader_name or task.downloader_id or ""},
                media=media,
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

    @staticmethod
    async def sync_existing_torrent_selection(
        client: DownloadClient,
        torrent_hash: str | None,
        selected_files: list[int] | None,
        files: list[TorrentFileItem] | None,
    ) -> None:
        if not client or not torrent_hash or not files:
            return
        num_files = len(files)
        valid_selected = sorted({idx for idx in selected_files if 0 <= idx < num_files}) if selected_files else list(range(num_files))
        if not valid_selected:
            return
        unselected = [idx for idx in range(num_files) if idx not in valid_selected]
        if unselected:
            await client.set_file_priority(torrent_hash, unselected, 0)
        await client.set_file_priority(torrent_hash, valid_selected, 1)

    async def create_download(self, req: DownloadTaskCreateInput, search_result: ResourceSearchResult) -> TaskData:
        if not search_result or search_result.result_id != req.result_id:
            raise InvalidRequestException("backendErrors.resultIdInvalidOrExpired")
        logger.debug("Preparing download request: media=%s result_id=%s title=%s", req.media.media_id, req.result_id, search_result.title)

        payload = build_torrent_payload(await torrent_service.fetch_blob(search_result), desc=search_result.description)
        torrent_service.store_blob(payload.metadata.hash if payload.metadata else None, payload.blob)
        download_target = self.resolve_download_target(req.directory_id)
        async with domain_lock_service.acquire_download_create(
            download_target.downloader_id,
            payload.metadata.hash,
        ) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.resourceDownloadCreating")

            existing_hash_tasks = [
                task
                for task in await self._repo.find_by_hash_and_downloader(
                    payload.metadata.hash,
                    download_target.downloader_id,
                )
                if task.status != TaskStatus.VOID
            ]
            existing_task = self._find_existing_task_for_context(
                tasks=existing_hash_tasks,
                req=req,
                download_path=download_target.download_path,
            )
            client = self._client_factory.get_download_client(download_target.downloader_id)
            if existing_task:
                return await self._expand_existing_task_selection(
                    task=existing_task,
                    hash_tasks=existing_hash_tasks,
                    requested_files=req.selected_files,
                    client=client,
                )
            if existing_hash_tasks:
                if not self._torrent_reuse_context_is_consistent(
                    tasks=existing_hash_tasks,
                    req=req,
                    download_path=download_target.download_path,
                ):
                    first_task = existing_hash_tasks[0]
                    logger.info(
                        "Download request blocked by existing task in different context: requested_media=%s requested_season=%s requested_directory=%s existing_task=%s existing_media=%s existing_season=%s existing_directory=%s hash=%s",
                        req.media.media_id,
                        req.media.season_number,
                        req.directory_id,
                        first_task.id,
                        first_task.context.media.media_id if first_task.context and first_task.context.media else None,
                        first_task.context.media.season_number if first_task.context and first_task.context.media else None,
                        first_task.context.directory_id if first_task.context else None,
                        first_task.torrent_hash,
                    )
                    raise DownloadTaskAlreadyExistsException()
                context = self.build_task_context(req, search_result, payload.metadata.attrs if payload.metadata else None)
                task = TaskData(
                    id=str(uuid.uuid4()),
                    media_id=req.media.media_id,
                    torrent_hash=payload.metadata.hash,
                    status=TaskStatus.DOWNLOADING,
                    context=context,
                    metadata=payload.metadata,
                    downloader_id=download_target.downloader_id,
                    save_path=to_download_relative_path(download_target.download_path),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                await self._repo.insert(task)
                await self.sync_existing_torrent_selection(
                    client,
                    task.torrent_hash,
                    self._selection_union([*existing_hash_tasks, task], task.metadata.files if task.metadata else []),
                    task.metadata.files if task.metadata else [],
                )
                logger.info(
                    "Download task attached to existing torrent: media=%s task=%s downloader=%s directory=%s hash=%s selected_files=%d",
                    task.media_id,
                    task.id,
                    task.downloader_id,
                    req.directory_id,
                    task.torrent_hash,
                    len(req.selected_files or []),
                )
                self.emit_download_started(task, req.media)
                return task
            await self._task_service.ensure_live_torrent_download_path_matches_hash(
                client,
                payload.metadata.hash,
                download_target.download_path,
            )

            context = self.build_task_context(req, search_result, payload.metadata.attrs if payload.metadata else None)
            task = TaskData(
                id=str(uuid.uuid4()),
                media_id=req.media.media_id,
                torrent_hash=payload.metadata.hash,
                status=TaskStatus.PENDING,
                context=context,
                metadata=payload.metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await self._repo.insert(task)

            file_priorities = self.build_file_priorities(req.selected_files, payload.metadata.files if payload.metadata else None)
            add_result = await client.add_torrent_file(
                torrent_data=payload.blob,
                save_path=download_target.download_path,
                category=download_target.download_category,
                file_priorities=file_priorities,
                tags=self.resolve_download_tags(),
            )
            if not add_result.success:
                await self._repo.delete_by_id(task.id)
                raise DownloadException(
                    "backendErrors.downloadTaskCreateFailed",
                    params={"reason": add_result.message or "add_torrent_failed"},
                )

            task.status = TaskStatus.DOWNLOADING
            task.downloader_id = download_target.downloader_id
            task.save_path = to_download_relative_path(download_target.download_path)
            task.updated_at = datetime.now()
            await self._repo.update_task(task)
            logger.info(
                "Download task queued: media=%s task=%s downloader=%s directory=%s hash=%s selected_files=%d reused=%s",
                task.media_id,
                task.id,
                task.downloader_id,
                req.directory_id,
                task.torrent_hash,
                len(req.selected_files or []),
                "false",
            )
            self.emit_download_started(task, req.media)
            return task
