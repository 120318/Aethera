from __future__ import annotations

from app.schemas.domain.command import CommandRecord, CommandResult, CommandStatus, CommandType


COMMAND_KEY_BY_TYPE = {
    CommandType.RESOURCE_SEARCH: "resourceSearch",
    CommandType.SUBSCRIPTION_RUN: "subscriptionRun",
    CommandType.TASK_CREATE: "taskCreate",
    CommandType.PILOT_EPISODE: "pilotEpisode",
    CommandType.TASK_PAUSE: "taskPause",
    CommandType.TASK_RESUME: "taskResume",
    CommandType.TASK_TRANSFER: "taskTransfer",
    CommandType.TASK_STORAGE_CHANGE: "taskStorageChange",
    CommandType.TASK_MEDIA_SERVER_SYNC: "taskMediaServerSync",
    CommandType.TASK_DANMU_GENERATE: "taskDanmuGenerate",
    CommandType.LIBRARY_FILE_DELETE: "libraryFileDelete",
    CommandType.LIBRARY_FILE_STORAGE_CHANGE: "libraryFileStorageChange",
    CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC: "libraryFileMediaServerSync",
    CommandType.LIBRARY_FILE_DANMU_GENERATE: "libraryFileDanmuGenerate",
    CommandType.TASK_DELETE: "taskDelete",
    CommandType.MEDIA_DELETE: "mediaDelete",
    CommandType.PROFILE_REFRESH: "profileRefresh",
    CommandType.DIRECTORY_INTEGRITY_SCAN: "directoryIntegrityScan",
    CommandType.DIRECTORY_INTEGRITY_REPAIR: "directoryIntegrityRepair",
}

STATUS_KEY_BY_STATUS = {
    CommandStatus.QUEUED: "queued",
    CommandStatus.RUNNING: "running",
    CommandStatus.SUCCEEDED: "succeeded",
    CommandStatus.FAILED: "failed",
    CommandStatus.CANCELLED: "cancelled",
}


def command_message_key(command_type: CommandType, status: CommandStatus) -> str:
    command_key = COMMAND_KEY_BY_TYPE[command_type]
    status_key = STATUS_KEY_BY_STATUS[status]
    return f"commandMessages.{command_key}.{status_key}"


def command_message_params(result: CommandResult | None) -> dict[str, str]:
    if result is None:
        return {}
    return {
        "result_count": str(result.result_count),
        "task_id": result.task_id or "",
        "transferred_files_count": str(result.transferred_files_count),
        "deleted_tasks_count": str(result.deleted_tasks_count),
        "deleted_library_files_count": str(result.deleted_library_files_count),
        "repaired_count": str(result.repaired_count),
        "failed_count": str(result.failed_count),
    }


def attach_command_message_i18n(command: CommandRecord) -> CommandRecord:
    command.message_key = command_message_key(command.type, command.status)
    command.message_params = command_message_params(command.result)
    return command
