import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandType, TaskDeleteCommandRequestPayload
from app.services.application.commands.service import command_service
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service

router = APIRouter()
logger = logging.getLogger(__name__)


class TaskDeleteCheckRequest(BaseModel):
    task_id: str


class TaskDeleteCheckResponse(BaseModel):
    task_id: str
    has_library_files: bool
    library_files_count: int


@router.post("/delete/check", response_model=TaskDeleteCheckResponse)
async def check_task_delete(body: TaskDeleteCheckRequest) -> TaskDeleteCheckResponse:
    if not body.task_id:
        raise RequestParamException("task_id", str(body.task_id))

    task = await download_service.find_task_by_id(body.task_id)
    task_key = task.id if task else body.task_id
    library_files = await library_service.get_files_by_task(task_key)

    cnt = len(library_files)
    return TaskDeleteCheckResponse(
        task_id=task_key,
        has_library_files=cnt > 0,
        library_files_count=cnt,
    )


class TaskDeleteRequest(BaseModel):
    task_id: str
    delete_files: bool = True
    force: bool = False
    delete_library_files: bool = False


@router.post("/delete", response_model=CommandResponse)
async def delete_task(body: TaskDeleteRequest) -> CommandResponse:
    if not body.task_id:
        raise RequestParamException("task_id", str(body.task_id))
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.TASK_DELETE,
            payload=TaskDeleteCommandRequestPayload(
                task_id=body.task_id,
                delete_files=body.delete_files,
                force=body.force,
                delete_library_files=body.delete_library_files,
            ),
        )
    )
    return CommandResponse(command=command)
