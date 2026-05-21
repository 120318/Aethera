from app.schemas.domain.action import ActionKind, ActionName, ActionRecord, ActionStatus
from app.services.audit.action_message_i18n import attach_action_message_i18n


def test_command_action_message_params_are_preserved():
    action = ActionRecord(
        kind=ActionKind.command,
        action_name=ActionName.resource_search.value,
        status=ActionStatus.completed,
        message_params={"result_count": "3"},
    )

    attach_action_message_i18n(action)

    assert action.message_key == "commandMessages.resourceSearch.succeeded"
    assert action.message_params == {"result_count": "3"}


def test_danmu_generate_no_danmu_skip_uses_specific_message_key():
    action = ActionRecord(
        kind=ActionKind.addon,
        action_name=ActionName.danmu_generate.value,
        status=ActionStatus.skipped,
        message_params={"reason": "no_danmu"},
    )

    attach_action_message_i18n(action)

    assert action.message_key == "actionMessages.danmuGenerate.notFound"


def test_danmu_generate_duration_mismatch_skip_uses_specific_message_key():
    action = ActionRecord(
        kind=ActionKind.addon,
        action_name=ActionName.danmu_generate.value,
        status=ActionStatus.skipped,
        message_params={"reason": "duration_mismatch"},
    )

    attach_action_message_i18n(action)

    assert action.message_key == "actionMessages.danmuGenerate.durationMismatch"
