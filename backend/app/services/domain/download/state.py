from __future__ import annotations

import logging
from datetime import datetime

from app.schemas.domain.download import TaskErrorStage, TaskFieldPatch, TaskStatus


logger = logging.getLogger("app.services.download")


class TaskStateService:
    def __init__(self, repo) -> None:
        self._repo = repo

    @staticmethod
    def is_valid_state_transition(current: str, new: TaskStatus) -> bool:
        transitions = {
            "ANY": [TaskStatus.VOID.value],
            TaskStatus.PENDING.value: [TaskStatus.DOWNLOADING.value, TaskStatus.MIGRATING.value],
            TaskStatus.DOWNLOADING.value: [TaskStatus.FINISHED.value, TaskStatus.PAUSED.value, TaskStatus.ERROR.value, TaskStatus.DOWNLOADING.value, TaskStatus.MIGRATING.value],
            TaskStatus.PAUSED.value: [TaskStatus.DOWNLOADING.value, TaskStatus.MIGRATING.value],
            TaskStatus.FINISHED.value: [TaskStatus.TRANSFERRING.value, TaskStatus.MIGRATING.value],
            TaskStatus.TRANSFERRING.value: [TaskStatus.COMPLETED.value, TaskStatus.ERROR.value, TaskStatus.FINISHED.value],
            TaskStatus.MIGRATING.value: [
                TaskStatus.PENDING.value,
                TaskStatus.DOWNLOADING.value,
                TaskStatus.PAUSED.value,
                TaskStatus.FINISHED.value,
                TaskStatus.COMPLETED.value,
                TaskStatus.PARTIAL_MISSING.value,
                TaskStatus.SEEDING_ABSENT.value,
                TaskStatus.FILE_MISSING.value,
                TaskStatus.ERROR.value,
            ],
            TaskStatus.COMPLETED.value: [
                TaskStatus.PARTIAL_MISSING.value,
                TaskStatus.SEEDING_ABSENT.value,
                TaskStatus.FILE_MISSING.value,
                TaskStatus.TRANSFERRING.value,
                TaskStatus.MIGRATING.value,
            ],
            TaskStatus.PARTIAL_MISSING.value: [
                TaskStatus.COMPLETED.value,
                TaskStatus.SEEDING_ABSENT.value,
                TaskStatus.FILE_MISSING.value,
                TaskStatus.TRANSFERRING.value,
                TaskStatus.MIGRATING.value,
            ],
            TaskStatus.SEEDING_ABSENT.value: [
                TaskStatus.COMPLETED.value,
                TaskStatus.PARTIAL_MISSING.value,
                TaskStatus.FILE_MISSING.value,
                TaskStatus.MIGRATING.value,
            ],
            TaskStatus.FILE_MISSING.value: [
                TaskStatus.COMPLETED.value,
                TaskStatus.PARTIAL_MISSING.value,
                TaskStatus.TRANSFERRING.value,
                TaskStatus.MIGRATING.value,
            ],
            TaskStatus.ERROR.value: [TaskStatus.PENDING.value, TaskStatus.TRANSFERRING.value, TaskStatus.FINISHED.value],
            TaskStatus.VOID.value: [TaskStatus.PENDING.value],
        }
        current_transitions = transitions[current] if current in transitions else []
        return new.value in transitions["ANY"] or new.value in current_transitions

    async def update_task_state(
        self,
        task_id: str,
        new_status: TaskStatus,
        error_key: str | None = None,
        progress: float | None = None,
        error_stage: TaskErrorStage | None = None,
        error_params: dict[str, str] | None = None,
    ) -> bool:
        task = await self._repo.find_by_id(task_id)
        if not task:
            return False
        current_status = task.status
        if not self.is_valid_state_transition(current_status, new_status):
            logger.warning("Invalid transition %s -> %s for %s", current_status, new_status, task_id)
            return False

        update_data = TaskFieldPatch(status=new_status, updated_at=datetime.now())
        if progress is not None:
            update_data.progress = progress
        if error_key is not None:
            update_data.error_key = error_key
            update_data.error_params = error_params or {}
        if error_stage is not None:
            update_data.error_stage = error_stage
        if new_status != TaskStatus.ERROR and error_key is None and (task.error_key is not None or task.error_stage is not None):
            update_data.error_key = None
            update_data.error_params = {}
            update_data.error_stage = None
        return await self._repo.update_fields(update_data, self._repo.cond_id(task_id))
