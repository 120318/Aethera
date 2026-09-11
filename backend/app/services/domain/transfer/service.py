from __future__ import annotations

import json
import logging
from enum import Enum
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
from .replacement import library_replacement_policy
from .ready_files import (
    ACTIVE_IMPORT_STATUSES,
    ReadyFileDisposition,
    inspect_ready_files,
    ready_file_indices,
    satisfied_file_indices,
    supports_early_import,
)


logger = logging.getLogger("app.services.transfer")


class TransferCommitMode(str, Enum):
    PARTIAL_INCREMENTAL = "partial_incremental"
    FINAL_INCREMENTAL = "final_incremental"
    FULL_IMPORT = "full_import"
    IDEMPOTENT_REPAIR = "idempotent_repair"

    @property
    def incremental(self) -> bool:
        return self in {self.PARTIAL_INCREMENTAL, self.FINAL_INCREMENTAL}

    @property
    def completes_task(self) -> bool:
        return self != self.PARTIAL_INCREMENTAL

    @property
    def preserves_existing(self) -> bool:
        return self == self.IDEMPOTENT_REPAIR


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
            if task.status == TaskStatus.FINISHED and supports_early_import(task):
                satisfied = await satisfied_file_indices(task, existing_files)
                if existing_files or satisfied:
                    return await self._finish_incremental_transfer(task, existing_files, satisfied)
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
        return await self._perform_incremental_transfer(
            task,
            existing_files,
            indices,
            TransferCommitMode.PARTIAL_INCREMENTAL,
        )

    async def _finish_incremental_transfer(
        self,
        task: TaskData,
        existing_files: list[LibraryFile],
        satisfied: set[int],
    ) -> TransferResult:
        selected = {
            index for index, _ in execution.iter_selected_files(task.metadata.files, execution.resolve_selected_indices(task))
        }
        remaining = selected - satisfied
        if remaining:
            inspection = await inspect_ready_files(
                task,
                existing_files,
                known_satisfied_indices=satisfied,
            )
            ready = set(inspection.indices)
            if not remaining.issubset(ready):
                if not ready:
                    missing_sources = await execution.missing_transfer_source_paths(task, remaining)
                    if missing_sources or inspection.disposition == ReadyFileDisposition.SOURCE_FALLBACK:
                        return await self._perform_incremental_transfer(
                            task, existing_files, remaining, TransferCommitMode.FINAL_INCREMENTAL,
                            handled_file_indices=selected,
                        )
                    if inspection.disposition == ReadyFileDisposition.WAIT:
                        return TransferResult(transferred_files=[])
                    await self._reject_terminal_file_validation(task)
                return await self._perform_incremental_transfer(
                    task, existing_files, ready, TransferCommitMode.PARTIAL_INCREMENTAL,
                )
        return await self._perform_incremental_transfer(
            task, existing_files, remaining, TransferCommitMode.FINAL_INCREMENTAL,
            handled_file_indices=selected,
        )

    async def _reject_terminal_file_validation(self, task: TaskData) -> None:
        exc = TransferException("backendErrors.transferSourceFilesNotReady")
        await self._lock_task_status(task)
        await emit_media_import_failed(task, exc.message_key, exc.params)
        await handle_transfer_error(task, exc.message_key, exc.params)
        raise exc

    async def _perform_incremental_transfer(
        self,
        task: TaskData,
        existing_files: list[LibraryFile],
        indices: set[int],
        commit_mode: TransferCommitMode,
        *,
        handled_file_indices: set[int] | None = None,
    ) -> TransferResult:
        try:
            if commit_mode.completes_task:
                await self._lock_task_status(task)
            if not indices:
                if commit_mode.completes_task:
                    ledger_indices = handled_file_indices if handled_file_indices is not None else indices
                    season_number = download_service.resolve_task_episode_coverage_detail(task).season_number
                    await library_service.replace_task_entries(
                        task.id,
                        task.context.directory_id,
                        task.media_id,
                        [],
                        season_number,
                        incremental=True,
                        imported_file_indices=sorted(ledger_indices),
                    )
                    task.context.imported_file_indices = sorted(
                        set(task.context.imported_file_indices) | ledger_indices
                    )
                    if not await download_service.update_task_state(task.id, TaskStatus.COMPLETED):
                        raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})
                return TransferResult(transferred_files=[])
            context = await execution.build_transfer_execution_context(task)
            context.selected_indices = indices
            transfer_plan = library_replacement_policy.select_batch_winners(
                execution.build_transfer_plan(task, context),
            )
            execution_report = await execution.execute_transfer_plan(task, context, transfer_plan)
            results = execution_report.materialized_files
            replacement_plan = await library_replacement_policy.build_plan(
                task,
                results,
                context.season_number,
                incremental=True,
            )
            await commit_transfer_results(
                task, results, existing_files, context, replacement_plan.replace_files,
                commit_mode=commit_mode,
                handled_file_indices=(
                    handled_file_indices
                    if handled_file_indices is not None
                    else indices
                ),
            )
            return TransferResult(transferred_files=results)
        except AppException as exc:
            await emit_media_import_failed(task, exc.message_key, exc.params)
            if commit_mode.completes_task:
                await handle_transfer_error(task, exc.message_key, exc.params)
            raise
        except (OSError, ValueError) as exc:
            error_key = "backendErrors.transferFailed"
            error_params = {"reason": str(exc)}
            await emit_media_import_failed(task, error_key, error_params)
            if commit_mode.completes_task:
                await handle_transfer_error(task, error_key, error_params)
            raise TransferException(error_key, params=error_params) from exc

    async def _perform_transfer(self, task: TaskData) -> TransferResult:
        logger.info("Starting transfer for task %s", task.id)
        try:
            await self._lock_task_status(task)
            existing_library_files = await library_service.get_files_by_task(task.id)
            execution_context = await execution.build_transfer_execution_context(task)
            full_transfer_plan = execution.build_transfer_plan(task, execution_context)
            transfer_plan = library_replacement_policy.select_batch_winners(full_transfer_plan)
            discarded_file_indices = {
                result.file_index for result in full_transfer_plan
            } - {
                result.file_index for result in transfer_plan
            }
            execution_report = await execution.execute_transfer_plan(task, execution_context, transfer_plan)
            transfer_results = execution_report.materialized_files
            replacement_plan = await library_replacement_policy.build_plan(task, transfer_results, execution_context.season_number)
            explicit_replacement_files = _include_discarded_batch_files(
                replacement_plan.replace_files,
                existing_library_files,
                discarded_file_indices,
            )
            await commit_transfer_results(
                task,
                transfer_results,
                existing_library_files,
                execution_context,
                explicit_replacement_files,
                commit_mode=(
                    TransferCommitMode.IDEMPOTENT_REPAIR
                    if execution_report.skipped_existing_files
                    else TransferCommitMode.FULL_IMPORT
                ),
                handled_file_indices={result.file_index for result in full_transfer_plan},
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
            raise TransferException(error_key, params=error_params) from exc

    async def _lock_task_status(self, task: TaskData) -> None:
        if not await download_service.update_task_state(task.id, TaskStatus.TRANSFERRING):
            raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})


def _include_discarded_batch_files(
    replacement_files: list[LibraryFile],
    existing_library_files: list[LibraryFile],
    discarded_file_indices: set[int],
) -> list[LibraryFile]:
    files_by_id = {item.id: item for item in replacement_files if item.id}
    for item in existing_library_files:
        if item.id and item.file_index in discarded_file_indices:
            files_by_id[item.id] = item
    return list(files_by_id.values())


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


def build_media_import_completed_event(
    task: TaskData,
    transfer_results: list[TransferFileResult],
) -> Event | None:
    primary_results = [
        result for result in transfer_results
        if file_name_looks_like_media_file(result.destination_path)
    ]
    if not primary_results:
        return None
    media = task.context.media
    if media is None:
        raise TransferException("backendErrors.transferMediaSnapshotMissing", params={"task_id": task.id, "media_id": str(task.media_id)})
    file_path = primary_results[0].destination_path
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
            file_path=file_path,
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
    *,
    commit_mode: TransferCommitMode = TransferCommitMode.FULL_IMPORT,
    handled_file_indices: set[int] | None = None,
) -> None:
    try:
        ledger_indices = (
            set(handled_file_indices)
            if handled_file_indices is not None
            else {result.file_index for result in transfer_results}
            if commit_mode.incremental and transfer_results
            else None
        )
        batch_paths = {str(Path(result.destination_path)) for result in transfer_results}
        incoming_video_paths = {
            str(Path(result.destination_path))
            for result in transfer_results
            if file_name_looks_like_media_file(result.destination_path)
        }
        sidecar_snapshots = await library_service.snapshot_replaced_sidecars(
            incoming_video_paths,
            batch_paths,
        )
        completion_event = (
            build_media_import_completed_event(task, transfer_results)
            if transfer_results
            else None
        )
        replaced_library_files = await library_service.replace_task_entries(
            task.id,
            task.context.directory_id,
            task.media_id,
            transfer_results,
            execution_context.season_number,
            replacement_files,
            incremental=commit_mode.incremental,
            preserve_existing=commit_mode.preserves_existing,
            imported_file_indices=sorted(ledger_indices) if ledger_indices is not None else None,
            completion_event=completion_event,
            dispatch_records=(
                event_service.build_dispatch_records(completion_event)
                if completion_event is not None
                else None
            ),
        )
        if ledger_indices is not None:
            task.context.imported_file_indices = sorted(
                set(task.context.imported_file_indices)
                | ledger_indices
            )
        replaced_video_paths = {
            str(build_library_file_path(item.path, item.file_name))
            for item in replaced_library_files
            if file_name_looks_like_media_file(item.file_name or "")
            and str(build_library_file_path(item.path, item.file_name)) in incoming_video_paths
        }
        await library_service.cleanup_replaced_sidecars(
            sidecar_snapshots,
            replaced_video_paths,
        )
        if commit_mode.completes_task:
            if not await download_service.update_task_state(task.id, TaskStatus.COMPLETED):
                raise TransferException("backendErrors.transferTaskLockFailed", params={"task_id": task.id})
        await cleanup_replaced_library_files(
            (
                replaced_library_files
                if commit_mode.incremental or commit_mode.preserves_existing
                else (replaced_library_files or existing_library_files)
            ),
            transfer_results,
        )
        if not transfer_results:
            return
        try:
            await media_service.refresh_profile_safely(task.media_id, execution_context.season_number)
        except AppException as exc:
            logger.warning("Failed to refresh profile after transfer for task %s: %s", task.id, exc)
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
