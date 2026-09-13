import logging
from datetime import datetime

from app.schemas.exception.exceptions import DownloadException, TransferException
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandType,
    TaskEpisodeBatchImportCommandRequestPayload,
    TaskTransferCommandRequestPayload,
)
from app.schemas.domain.download import BatchJobResult, TaskData, TaskErrorStage, TaskStatus
from app.services.application.commands.service import CommandConflictException, command_service
from app.services.domain.download import download_service
from app.services.domain.transfer.execution import missing_transfer_source_paths
from app.services.domain.transfer.episode_batch import find_ready_episode_file_indices

logger = logging.getLogger("app.services.scheduled_transfer_command")

SOURCE_VISIBILITY_GRACE_SECONDS = 120


def _source_visibility_grace_elapsed(task: TaskData, now: datetime | None = None) -> bool:
    if not task.updated_at:
        return True
    return ((now or datetime.now()) - task.updated_at).total_seconds() >= SOURCE_VISIBILITY_GRACE_SECONDS


async def _mark_precheck_transfer_failed(task: TaskData, exc: TransferException) -> None:
    try:
        await download_service.update_task_state(
            task.id,
            TaskStatus.FINISHED,
            error_key=exc.message_key,
            error_params={str(key): str(value) for key, value in exc.params.items()},
            error_stage=TaskErrorStage.TRANSFER,
        )
    except DownloadException as update_exc:
        logger.error("Failed to mark scheduled transfer precheck failure for task %s: %s", task.id, update_exc)


class ScheduledTransferCommandService:
    async def enqueue_import_tasks(self) -> BatchJobResult:
        early_result = await self.enqueue_ready_episode_batches()
        finished_result = await self.enqueue_finished_tasks()
        return BatchJobResult(
            processed=early_result.processed + finished_result.processed,
            completed=early_result.completed + finished_result.completed,
            errors=early_result.errors + finished_result.errors,
        )

    async def enqueue_ready_episode_batches(self) -> BatchJobResult:
        tasks = await download_service.get_tasks(status=[TaskStatus.DOWNLOADING, TaskStatus.PAUSED])
        if not tasks:
            return BatchJobResult()
        statuses = await download_service.get_torrent_status_by_tasks(tasks)
        processed = 0
        completed = 0
        errors = 0
        for task in tasks:
            processed += 1
            try:
                torrent_status = statuses[task.id] if task.id in statuses else None
                file_indices = await find_ready_episode_file_indices(task, torrent_status)
                if not file_indices:
                    continue
                await command_service.create_command(
                    CommandCreateRequest(
                        type=CommandType.TASK_EPISODE_BATCH_IMPORT,
                        initiator=CommandInitiator.SCHEDULER,
                        payload=TaskEpisodeBatchImportCommandRequestPayload(
                            task_id=task.id,
                            file_indices=file_indices,
                        ),
                    )
                )
                completed += 1
            except CommandConflictException:
                logger.info("Episode batch import command already exists for task %s", task.id)
            except (DownloadException, TransferException, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Failed to enqueue episode batch import for task %s: %s", task.id, exc)
                errors += 1
        return BatchJobResult(processed=processed, completed=completed, errors=errors)

    async def enqueue_finished_tasks(self) -> BatchJobResult:
        finished_tasks = await download_service.get_tasks(status=[TaskStatus.FINISHED])
        if not finished_tasks:
            return BatchJobResult()

        processed = 0
        completed = 0
        errors = 0

        for task in finished_tasks:
            processed += 1
            try:
                missing_sources = await missing_transfer_source_paths(task)
                if missing_sources:
                    if not _source_visibility_grace_elapsed(task):
                        logger.info(
                            "Scheduled transfer delayed until source files are visible: task=%s missing=%s",
                            task.id,
                            missing_sources[:3],
                        )
                        continue
                    logger.warning(
                        "Scheduled transfer source files still missing after grace period; enqueueing transfer for visible failure handling: task=%s missing=%s",
                        task.id,
                        missing_sources[:3],
                    )
                await command_service.create_command(
                    CommandCreateRequest(
                        type=CommandType.TASK_TRANSFER,
                        initiator=CommandInitiator.SCHEDULER,
                        payload=TaskTransferCommandRequestPayload(task_id=task.id),
                    )
                )
                completed += 1
            except CommandConflictException:
                logger.info("Scheduled transfer command already exists for task %s", task.id)
            except TransferException as exc:
                logger.error("Scheduled transfer precheck failed for task %s: %s", task.id, exc)
                await _mark_precheck_transfer_failed(task, exc)
                errors += 1
            except (DownloadException, RuntimeError, ValueError) as exc:
                logger.error("Failed to enqueue scheduled transfer for task %s: %s", task.id, exc)
                errors += 1

        return BatchJobResult(processed=processed, completed=completed, errors=errors)


scheduled_transfer_command_service = ScheduledTransferCommandService()
