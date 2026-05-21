from __future__ import annotations

from collections.abc import Mapping

from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandResult, CommandType
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.commands.contract import CommandHandler


class CommandHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[CommandType, CommandHandler] = {}

    def register(self, handler: CommandHandler) -> None:
        self._handlers[handler.command_type] = handler

    def registered_handlers(self) -> Mapping[CommandType, CommandHandler]:
        return self._handlers

    async def build_command(self, body: CommandCreateRequest) -> CommandRecord:
        if body.type not in self._handlers:
            raise RequestParamException("type", str(body.type))
        return await self._handlers[body.type].build(body)

    async def execute(self, command: CommandRecord) -> CommandResult:
        if command.type not in self._handlers:
            raise RequestParamException("type", str(command.type))
        return await self._handlers[command.type].execute(command)

    def resolve_running_message(self, command_type: CommandType) -> str:
        if command_type not in self._handlers:
            raise RequestParamException("type", str(command_type))
        return self._handlers[command_type].resolve_running_message()

    def resolve_success_message(self, command_type: CommandType, result: CommandResult) -> str:
        if command_type not in self._handlers:
            raise RequestParamException("type", str(command_type))
        return self._handlers[command_type].resolve_success_message(result)

    def resolve_failed_message(self, command_type: CommandType) -> str:
        if command_type not in self._handlers:
            raise RequestParamException("type", str(command_type))
        return self._handlers[command_type].resolve_failed_message()

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        if command.type not in self._handlers:
            raise RequestParamException("type", str(command.type))
        return self._handlers[command.type].resolve_action_context(command)
