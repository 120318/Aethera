import logging
from datetime import datetime

from app.schemas.exception.exceptions import DownloadException, TransferException
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandType, TaskTransferCommandRequestPayload
from app.schemas.domain.download import BatchJobResult, TaskData, TaskErrorStage, TaskStatus
from app.services.application.commands.service import CommandConflictException, command_service
from app.services.domain.download import download_service
from app.services.domain.transfer.execution import missing_transfer_source_paths
from app.services.domain.transfer.ready_files import ACTIVE_IMPORT_STATUSES, find_ready_file_indices
from app.services.platform.domain_lock_service import domain_lock_service

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
    async def enqueue_ready_files(self) -> BatchJobResult:
        tasks = await download_service.get_tasks(status=ACTIVE_IMPORT_STATUSES)
        result = BatchJobResult(processed=len(tasks))
        for task in tasks:
            try:
                if await domain_lock_service.is_task_op_locked(task.id):
                    continue
                indices = await find_ready_file_indices(task)
                if not indices:
                    continue
                await command_service.create_command(
                    CommandCreateRequest(
                        type=CommandType.TASK_TRANSFER,
                        initiator=CommandInitiator.SCHEDULER,
                        payload=TaskTransferCommandRequestPayload(task_id=task.id, file_indices=indices),
                    )
                )
                result.completed += 1
            except CommandConflictException:
                continue
            except (DownloadException, TransferException, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Failed to schedule completed files: task=%s error=%s", task.id, exc)
                result.errors += 1
        return result

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
