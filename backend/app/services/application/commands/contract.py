from __future__ import annotations

from typing import Protocol

from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandResult, CommandType
from app.schemas.runtime.command_runtime import CommandActionContext


class CommandHandler(Protocol):
    command_type: CommandType

    async def build(self, body: CommandCreateRequest) -> CommandRecord: ...

    async def execute(self, command: CommandRecord) -> CommandResult: ...

    def resolve_running_message(self) -> str: ...

    def resolve_success_message(self, result: CommandResult) -> str: ...

    def resolve_failed_message(self) -> str: ...

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext: ...
