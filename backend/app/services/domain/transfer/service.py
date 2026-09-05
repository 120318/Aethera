from __future__ import annotations

import json
import logging
from pathlib import Path

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.addon_events import MediaImportFailedEventMeta
from app.schemas.domain.download import TaskData, TaskErrorStage, TaskStatus, TransferFileResult, TransferResult
from app.schemas.domain.event import EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.library import LibraryFile
from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import TransferException
from app.services.audit.event_service import event_service
from app.services.domain.download import download_service
from app.services.domain.download.task_runtime_service import event_actor_for_task
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.fs_utils import fs_provider
from app.utils.library_paths import build_library_file_path

from . import execution
from .execution import TransferExecutionContext
from .replacement import library_replacement_policy
from .ready_files import ACTIVE_IMPORT_STATUSES, present_file_indices, ready_file_indices, supports_early_import


logger = logging.getLogger("app.services.transfer")


def _nested_message_params(params: dict[str, str] | None) -> str:
    if not params:
        return ""
    return json.dumps(
        {str(key): str(value) for key, value in params.items() if value is not None},
        ensure_ascii=False,
        sort_keys=True,
    )


class TransferService:
    async def perform_transfer_by_task_id(self, task_id: str, *, file_indices: list[int] | None = None) -> TransferResult:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise TransferException("backendErrors.taskBusy")
            task = await download_service.find_task_by_id(task_id)
            if not task:
                raise TransferException("backendErrors.taskNotFound", params={"id": task_id})
            existing_files = await library_service.get_files_by_task(task.id)
            if file_indices is not None or task.status in ACTIVE_IMPORT_STATUSES:
                return await self._perform_ready_transfer(task, existing_files, file_indices)
            if task.status == TaskStatus.FINISHED and existing_files and supports_early_import(task):
                return await self._finish_incremental_transfer(task, existing_files)
            skip_result = await execution.validate_transfer_reentry(task, existing_files)
            if skip_result is not None:
                return skip_result
            return await self._perform_transfer(task)

    async def _perform_ready_transfer(
        self, task: TaskData, existing_files: list[LibraryFile], file_indices: list[int] | None,
    ) -> TransferResult:
        # Recheck after acquiring the task lock: selection, downloader and progress
        # can all change while a command is queued. An empty subset means no work.
        indices = set(await ready_file_indices(task, existing_files))
        if file_indices is not None:
            indices.intersection_update(file_indices)
        if not indices:
            return TransferResult(transferred_files=[])
        return await self._perform_incremental_transfer(task, existing_files, indices, complete=False)

    async def _finish_incremental_transfer(self, task: TaskData, existing_files: list[LibraryFile]) -> TransferResult:
        selected = {
            index for index, _ in execution.iter_selected_files(task.metadata.files, execution.resolve_selected_indices(task))
        }
        remaining = selected - present_file_indices(existing_files)
        if remaining:
            ready = set(await ready_file_indices(task, existing_files))
            if not remaining.issubset(ready):
                if not ready:
                    return TransferResult(transferred_files=[])
                return await self._perform_incremental_transfer(task, existing_files, ready, complete=False)
        return await self._perform_incremental_transfer(task, existing_files, remaining, complete=True)

    async def _perform_incremental_transfer(
        self, task: TaskData, existing_files: list[LibraryFile], indices: set[int], *, complete: bool,
    ) -> TransferResult:
        try:
            if complete:
                await self._lock_task_status(task)
            context = await execution.build_transfer_execution_context(task)
            context.selected_indices = indices
            results = await execution.execute_transfer(task, context)
            replacement_plan = await library_replacement_policy.build_plan(task, results, context.season_number)
            await commit_transfer_results(
                task, results, existing_files, context, replacement_plan.replace_files,
                incremental=True, complete=complete,
            )
            return TransferResult(transferred_files=results)
        except AppException as exc:
            await emit_media_import_failed(task, exc.message_key, exc.params)
            if complete:
                await handle_transfer_error(task, exc.message_key, exc.params)
            raise
        except (OSError, ValueError) as exc:
            error_key = "backendErrors.transferFailed"
            error_params = {"reason": str(exc)}
            await emit_media_import_failed(task, error_key, error_params)
            if complete:
                await handle_transfer_error(task, error_key, error_params)
            raise

    async def _perform_transfer(self, task: TaskData) -> TransferResult:
        logger.info("Starting transfer for task %s", task.id)
        try:
            await self._lock_task_status(task)
            existing_library_files = await library_service.get_files_by_task(task.id)
            execution_context = await execution.build_transfer_execution_context(task)
            transfer_results = await execution.execute_transfer(task, execution_context)
            replacement_plan = await library_replacement_policy.build_plan(task, transfer_results, execution_context.season_number)
            await commit_transfer_results(
                task,
                transfer_results,
                existing_library_files,
                execution_context,
                replacement_plan.replace_files,
            )
            logger.info("Transfer completed: task=%s files=%d", task.id, len(transfer_results))
            return TransferResult(transferred_files=transfer_results)
        except AppException as exc:
            await emit_media_import_failed(task, exc.message_key, exc.params)
            await handle_transfer_error(task, exc.message_key, exc.params)
            raise
        except (OSError, ValueError) as exc:
            error_key = "backendErrors.transferFailed"
            error_params = {"reason": str(exc)}
            await emit_media_import_failed(task, error_key, error_params)
            await handle_transfer_error(task, error_key, error_params)
            raise

    async def _lock_task_status(self, task: TaskData) -> None:
        if not await download_service.update_task_state(task.id, TaskStatus.TRANSFERRING):
            raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})


def cleanup_replaced_library_files(
    existing_library_files: list[LibraryFile],
    transfer_results: list[TransferFileResult],
) -> None:
    if not existing_library_files:
        return
    replacement_paths = {str(Path(result.destination_path)) for result in transfer_results}
    for library_file in existing_library_files:
        full_path = build_library_file_path(library_file.path, library_file.file_name)
        if str(full_path) in replacement_paths or not fs_provider.exists(full_path):
            continue
        try:
            fs_provider.remove(full_path)
        except OSError as exc:
            logger.warning("Failed to remove replaced library file %s: %s", full_path, exc)


def _task_import_entities(task: TaskData) -> list[EventEntityRef]:
    return [EventEntityRef(type="task", id=task.id), EventEntityRef(type="media", id=str(task.media_id))]


async def emit_media_import_completed(task: TaskData, transfer_results: list[TransferFileResult]) -> None:
    try:
        media = task.context.media
        if media is None:
            raise TransferException("backendErrors.transferMediaSnapshotMissing", params={"task_id": task.id, "media_id": str(task.media_id)})
        file_path = transfer_results[0].destination_path if transfer_results else ""
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.MEDIA_IMPORT_COMPLETED,
                media=media,
                task_id=task.id,
                actor=event_actor_for_task(task),
                source=EventSource.base,
                entities=_task_import_entities(task),
            ),
            meta=MediaImportCompletedEventMeta(
                task_id=task.id,
                directory_id=task.context.directory_id,
                media_id=task.media_id,
                resource_title=task.context.resource_title,
                torrent_name=task.metadata.name if task.metadata else None,
                file_path=file_path,
                imported_files=[
                    ImportedMediaFile(
                        destination_path=result.destination_path,
                        episode_number=result.episode_number,
                        episode_numbers=result.episode_numbers,
                    )
                    for result in transfer_results
                ],
            ),
        )
    except AppException as exc:
        logger.warning("Failed to emit media import event for task %s: %s", task.id, exc)


async def emit_media_import_failed(task: TaskData, error_key: str, error_params: dict[str, str] | None = None) -> None:
    try:
        media = task.context.media
        if media is None:
            raise TransferException("backendErrors.transferMediaSnapshotMissing", params={"task_id": task.id, "media_id": str(task.media_id)})
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.MEDIA_IMPORT_FAILED,
                level=EventLevel.error,
                media=media,
                task_id=task.id,
                actor=event_actor_for_task(task),
                source=EventSource.base,
                entities=_task_import_entities(task),
            ),
            meta=MediaImportFailedEventMeta(
                task_id=task.id,
                directory_id=task.context.directory_id,
                media_id=task.media_id,
                resource_title=task.context.resource_title,
                torrent_name=task.metadata.name if task.metadata else None,
                error=error_key,
                error_key=error_key,
                error_params=error_params or {},
            ),
        )
    except AppException as exc:
        logger.warning("Failed to emit media import failed event for task %s: %s", task.id, exc)


async def commit_transfer_results(
    task: TaskData,
    transfer_results: list[TransferFileResult],
    existing_library_files: list[LibraryFile],
    execution_context: TransferExecutionContext,
    replacement_files: list[LibraryFile] | None = None,
    *,
    incremental: bool = False,
    complete: bool = True,
) -> None:
    try:
        replaced_library_files = await library_service.replace_task_entries(
            task.id,
            task.context.directory_id,
            task.media_id,
            transfer_results,
            execution_context.season_number,
            replacement_files,
            incremental=incremental,
        )
        if complete:
            if not await download_service.update_task_state(task.id, TaskStatus.COMPLETED):
                raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})
        cleanup_replaced_library_files(
            replaced_library_files if incremental else (replaced_library_files or existing_library_files), transfer_results,
        )
        if not transfer_results:
            return
        try:
            await media_service.refresh_profile_safely(task.media_id, execution_context.season_number)
        except AppException as exc:
            logger.warning("Failed to refresh profile after transfer for task %s: %s", task.id, exc)
        await emit_media_import_completed(task, transfer_results)
    except AppException as exc:
        raise TransferException("backendErrors.transferCommitFailed", params={"reason_key": exc.message_key})


async def handle_transfer_error(task: TaskData, error_key: str, error_params: dict[str, str] | None = None) -> None:
    try:
        await download_service.update_task_state(
            task.id,
            TaskStatus.FINISHED,
            error_key=error_key,
            error_params=error_params,
            error_stage=TaskErrorStage.TRANSFER,
        )
    except AppException as exc:
        logger.error("Failed to update error status: %s", exc)


transfer_service = TransferService()
