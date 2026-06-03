import logging
from datetime import datetime

from app.schemas.exception.exceptions import DownloadException
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandType, TaskTransferCommandRequestPayload
from app.schemas.domain.download import BatchJobResult, TaskData, TaskStatus
from app.services.application.commands.service import CommandConflictException, command_service
from app.services.domain.download import download_service
from app.services.domain.transfer.execution import missing_transfer_source_paths

logger = logging.getLogger("app.services.scheduled_transfer_command")

SOURCE_VISIBILITY_GRACE_SECONDS = 120


def _source_visibility_grace_elapsed(task: TaskData, now: datetime | None = None) -> bool:
    if not task.updated_at:
        return True
    return ((now or datetime.now()) - task.updated_at).total_seconds() >= SOURCE_VISIBILITY_GRACE_SECONDS


class ScheduledTransferCommandService:
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
            except (DownloadException, RuntimeError, ValueError) as exc:
                logger.error("Failed to enqueue scheduled transfer for task %s: %s", task.id, exc)
                errors += 1

        return BatchJobResult(processed=processed, completed=completed, errors=errors)


scheduled_transfer_command_service = ScheduledTransferCommandService()
