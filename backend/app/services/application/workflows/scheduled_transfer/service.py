import logging

from app.schemas.exception.exceptions import DownloadException
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandType, TaskTransferCommandRequestPayload
from app.schemas.domain.download import BatchJobResult, TaskStatus
from app.services.application.commands.service import CommandConflictException, command_service
from app.services.domain.download import download_service

logger = logging.getLogger("app.services.scheduled_transfer_command")


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
