from __future__ import annotations

from app.schemas.domain.action import ActionKind, ActionName, ActionRecord, ActionStatus
from app.schemas.domain.command import CommandStatus, CommandType
from app.services.application.commands.message_i18n import command_message_key


COMMAND_STATUS_BY_ACTION_STATUS = {
    ActionStatus.queued: CommandStatus.QUEUED,
    ActionStatus.running: CommandStatus.RUNNING,
    ActionStatus.completed: CommandStatus.SUCCEEDED,
    ActionStatus.failed: CommandStatus.FAILED,
    ActionStatus.cancelled: CommandStatus.CANCELLED,
}

ACTION_STATUS_KEY_BY_STATUS = {
    ActionStatus.queued: "queued",
    ActionStatus.running: "running",
    ActionStatus.completed: "completed",
    ActionStatus.failed: "failed",
    ActionStatus.cancelled: "cancelled",
    ActionStatus.skipped: "skipped",
}


def action_message_key(action: ActionRecord) -> str | None:
    if action.kind == ActionKind.command:
        try:
            command_type = CommandType(action.action_name)
        except ValueError:
            return None
        command_status = COMMAND_STATUS_BY_ACTION_STATUS.get(action.status)
        if command_status is None:
            return None
        return command_message_key(command_type, command_status)

    status_key = ACTION_STATUS_KEY_BY_STATUS[action.status]
    reason = action.message_params["reason"] if "reason" in action.message_params else None
    if (
        action.action_name == ActionName.danmu_generate.value
        and action.status == ActionStatus.skipped
        and reason == "no_danmu"
    ):
        return "actionMessages.danmuGenerate.notFound"
    if (
        action.action_name == ActionName.danmu_generate.value
        and action.status == ActionStatus.skipped
        and reason == "duration_mismatch"
    ):
        return "actionMessages.danmuGenerate.durationMismatch"
    if action.kind == ActionKind.scheduler:
        return f"actionMessages.scheduler.{status_key}"
    if action.kind == ActionKind.addon:
        return f"actionMessages.addon.{status_key}"
    return f"actionMessages.generic.{status_key}"


def attach_action_message_i18n(action: ActionRecord) -> ActionRecord:
    action.message_key = action_message_key(action)
    if action.kind != ActionKind.command:
        action.message_params = {}
    return action
