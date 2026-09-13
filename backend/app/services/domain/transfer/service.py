from __future__ import annotations

import json
import logging
from pathlib import Path

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.addon_events import MediaImportFailedEventMeta
from app.schemas.domain.download import TaskData, TaskErrorStage, TaskStatus, TransferFileResult, TransferResult
from app.schemas.domain.event import Event, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.library import LibraryFile
from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import TransferException
from app.services.audit.event_service import event_service
from app.services.domain.download import download_service
from app.services.domain.download.task_runtime_service import event_actor_for_task
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file

from . import execution
from .execution import TransferExecutionContext
from .episode_batch import (
    EARLY_IMPORT_TASK_STATUSES,
    find_ready_episode_file_indices,
    remaining_selected_file_indices,
)
from .replacement import library_replacement_policy


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
    async def perform_transfer_by_task_id(self, task_id: str) -> TransferResult:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise TransferException("backendErrors.taskBusy")
            task = await download_service.find_task_by_id(task_id)
            if not task:
                raise TransferException("backendErrors.taskNotFound", params={"id": task_id})
            if task.status == TaskStatus.FINISHED and task.context.imported_file_indices:
                return await self._finish_episode_batches(task)
            existing_files = await library_service.get_files_by_task(task.id)
            skip_result = await execution.validate_transfer_reentry(task, existing_files)
            if skip_result is not None:
                return skip_result
            return await self._perform_transfer(task)

    async def import_episode_batch(self, task_id: str, captured_file_indices: list[int]) -> TransferResult:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise TransferException("backendErrors.taskBusy")
            task = await download_service.find_task_by_id(task_id)
            if not task:
                raise TransferException("backendErrors.taskNotFound", params={"id": task_id})
            if task.status not in EARLY_IMPORT_TASK_STATUSES:
                return TransferResult(transferred_files=[])
            statuses = await download_service.get_torrent_status_by_tasks([task])
            torrent_status = statuses[task.id] if task.id in statuses else None
            ready = set(await find_ready_episode_file_indices(task, torrent_status))
            ready.intersection_update(int(index) for index in captured_file_indices)
            if not ready:
                return TransferResult(transferred_files=[])
            return await self._perform_episode_batch(task, ready, completes_task=False)

    async def _finish_episode_batches(self, task: TaskData) -> TransferResult:
        try:
            await self._lock_task_status(task)
            remaining = remaining_selected_file_indices(task)
            if not remaining:
                if not await download_service.update_task_state(task.id, TaskStatus.COMPLETED):
                    raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})
                return TransferResult(transferred_files=[])
            return await self._perform_episode_batch(task, remaining, completes_task=True)
        except AppException as exc:
            await emit_media_import_failed(task, exc.message_key, exc.params)
            await handle_transfer_error(task, exc.message_key, exc.params)
            raise

    async def _perform_episode_batch(
        self,
        task: TaskData,
        file_indices: set[int],
        *,
        completes_task: bool,
    ) -> TransferResult:
        try:
            context = await execution.build_transfer_execution_context(task)
            context.selected_indices = file_indices
            transfer_plan = execution.build_transfer_plan(task, context)
            transfer_results = await execution.execute_transfer_plan(task, context, transfer_plan)
            replacement_plan = await library_replacement_policy.build_plan(
                task,
                transfer_results,
                context.season_number,
            )
            replacement_files = await library_replacement_policy.keep_complete_episode_replacements(
                task,
                transfer_results,
                replacement_plan.replace_files,
                context.season_number,
            )
            await commit_episode_batch(
                task,
                transfer_results,
                context,
                replacement_files,
                handled_file_indices=file_indices,
            )
            if completes_task and not await download_service.update_task_state(task.id, TaskStatus.COMPLETED):
                raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})
            return TransferResult(transferred_files=transfer_results)
        except AppException:
            raise
        except (OSError, ValueError) as exc:
            error_key = "backendErrors.transferFailed"
            error_params = {"reason": str(exc)}
            raise TransferException(error_key, params=error_params) from exc

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


async def cleanup_replaced_library_files(
    existing_library_files: list[LibraryFile],
    transfer_results: list[TransferFileResult],
) -> None:
    if not existing_library_files:
        return
    replacement_paths = {str(Path(result.destination_path)) for result in transfer_results}
    await library_service.cleanup_replaced_files(existing_library_files, replacement_paths)


def _task_import_entities(task: TaskData) -> list[EventEntityRef]:
    return [EventEntityRef(type="task", id=task.id), EventEntityRef(type="media", id=str(task.media_id))]


async def emit_media_import_completed(task: TaskData, transfer_results: list[TransferFileResult]) -> None:
    try:
        event = build_media_import_completed_event(task, transfer_results)
        if event is not None:
            event_service.repo.insert(event)
            event_service.dispatch_persisted_event(event)
    except AppException as exc:
        logger.warning("Failed to emit media import event for task %s: %s", task.id, exc)


def build_media_import_completed_event(
    task: TaskData,
    transfer_results: list[TransferFileResult],
) -> Event | None:
    primary_results = [
        result
        for result in transfer_results
        if file_name_looks_like_media_file(result.destination_path)
    ]
    if not primary_results:
        return None
    media = task.context.media
    if media is None:
        raise TransferException(
            "backendErrors.transferMediaSnapshotMissing",
            params={"task_id": task.id, "media_id": str(task.media_id)},
        )
    return event_service.build_media_event(
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
            file_path=primary_results[0].destination_path,
            imported_files=[
                ImportedMediaFile(
                    destination_path=result.destination_path,
                    episode_number=result.episode_number,
                    episode_numbers=result.episode_numbers,
                )
                for result in primary_results
            ],
        ),
    )


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
) -> None:
    try:
        replaced_library_files = await library_service.replace_task_entries(
            task.id,
            task.context.directory_id,
            task.media_id,
            transfer_results,
            execution_context.season_number,
            replacement_files,
        )
        await download_service.update_task_state(task.id, TaskStatus.COMPLETED)
        await cleanup_replaced_library_files(replaced_library_files or existing_library_files, transfer_results)
        try:
            await media_service.refresh_profile_safely(task.media_id, execution_context.season_number)
        except AppException as exc:
            logger.warning("Failed to refresh profile after transfer for task %s: %s", task.id, exc)
        await emit_media_import_completed(task, transfer_results)
    except AppException as exc:
        raise TransferException("backendErrors.transferCommitFailed", params={"reason_key": exc.message_key})


async def commit_episode_batch(
    task: TaskData,
    transfer_results: list[TransferFileResult],
    execution_context: TransferExecutionContext,
    replacement_files: list[LibraryFile],
    *,
    handled_file_indices: set[int],
) -> None:
    try:
        completion_event = build_media_import_completed_event(task, transfer_results)
        removed_files = await library_service.replace_task_batch_entries(
            task.id,
            task.context.directory_id,
            task.media_id,
            transfer_results,
            sorted(handled_file_indices),
            execution_context.season_number,
            replacement_files,
            completion_event,
            event_service.build_dispatch_records(completion_event) if completion_event else None,
        )
        task.context.imported_file_indices = sorted(
            set(task.context.imported_file_indices) | handled_file_indices
        )
        await cleanup_replaced_library_files(removed_files, transfer_results)
        if transfer_results:
            try:
                await media_service.refresh_profile_safely(task.media_id, execution_context.season_number)
            except AppException as exc:
                logger.warning("Failed to refresh profile after episode batch for task %s: %s", task.id, exc)
    except AppException as exc:
        raise TransferException("backendErrors.transferCommitFailed", params={"reason_key": exc.message_key}) from exc


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
