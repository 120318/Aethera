from __future__ import annotations

import logging
import uuid

from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import ResourceNotFoundException, SystemException
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    PilotEpisodeCommandRecordPayload,
    TaskCreateCommandRecordPayload,
    TaskDanmuGenerateCommandRecordPayload,
    TaskDeleteCommandRecordPayload,
    TaskMediaServerSyncCommandRecordPayload,
    TaskPauseCommandRecordPayload,
    TaskResumeCommandRecordPayload,
    TaskStorageChangeCommandRecordPayload,
    TaskTransferCommandRecordPayload,
)
from app.schemas.domain.media import MediaTarget
from app.schemas.runtime.command_runtime import CommandActionContext
from app.schemas.domain.download import DownloadTaskCreateInput, TaskData
from app.services.domain.download.downloader_change import TaskDownloaderChangeRequest
from app.services.application.commands.target_labels import format_media_target_label
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.media_server_sync.service import media_server_sync_service
from app.services.application.workflows.resource_search import resource_search_service
from app.services.application.workflows.subscription.pilot import pilot_download_application_service
from app.services.domain.download import download_service
from app.services.domain.media import media_service
from app.services.domain.transfer import transfer_service

logger = logging.getLogger("app.services.command.download")


def _task_media_target(task: TaskData) -> MediaTarget:
    coverage = download_service.resolve_task_episode_coverage_detail(task)
    return MediaTarget(
        media_id=task.media_id,
        season_number=coverage.season_number if coverage.has_known_season else None,
    )


class TaskCommandSupport:
    command_type: CommandType

    async def _resolve_task(self, task_id: str) -> TaskData:
        task = await download_service.find_task_by_id(task_id)
        if task:
            return task
        raise ResourceNotFoundException("backendErrors.taskNotFound")

    def _resolve_task_label(self, task: TaskData | None) -> str:
        context = task.context if task else None
        metadata = task.metadata if task else None
        if context and context.resource_title:
            return context.resource_title
        if metadata and metadata.name:
            return metadata.name
        return task.id if task else ""

    def _build_task_command_record(
        self,
        *,
        body: CommandCreateRequest,
        task: TaskData,
        payload,
        uniq_key: str,
    ) -> CommandRecord:
        target = _task_media_target(task)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=self.command_type,
            payload=payload,
            initiator=body.initiator,
            media_id=task.media_id,
            target=target,
            uniq_key=uniq_key,
            target_type=CommandTargetType.TASK,
            target_id=task.id,
            target_label=self._resolve_task_label(task),
        )

    def _resolve_task_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id, task_id=payload.resolved_task_id)


class TaskCreateCommandHandler:
    command_type = CommandType.TASK_CREATE

    def _build_uniq_key(self, request: DownloadTaskCreateInput) -> str:
        selected_files = ",".join(str(item) for item in sorted(request.selected_files or []))
        return (
            f"command:{CommandType.TASK_CREATE.value}:{request.media.media_id}:"
            f"result_id={request.result_id}:directory_id={request.directory_id}:selected_files={selected_files}"
        )

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        target_label = format_media_target_label(request.media)
        search_result = resource_search_service.get_by_result_id(request.result_id)
        payload = TaskCreateCommandRecordPayload(
            media=request.media,
            result_id=request.result_id,
            directory_id=request.directory_id,
            selected_files=request.selected_files,
            resource_title=search_result.title if search_result else None,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.TASK_CREATE,
            payload=payload,
            initiator=body.initiator,
            media_id=request.media.media_id,
            target=MediaTarget(media_id=request.media.media_id, season_number=request.media.season_number),
            uniq_key=self._build_uniq_key(request),
            target_type=CommandTargetType.MEDIA,
            target_id=str(request.media.media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        search_result = resource_search_service.get_by_result_id(payload.result_id)
        if not search_result:
            raise ResourceNotFoundException("backendErrors.resultIdInvalidOrExpired")
        task = await download_service.create_download(
            DownloadTaskCreateInput(
                media=payload.media,
                result_id=payload.result_id,
                directory_id=payload.directory_id,
                selected_files=payload.selected_files,
            ),
            search_result,
        )
        try:
            await media_service.upsert_active_profile_from_identity(payload.media)
        except AppException as exc:
            logger.warning(
                "Download task created but media profile upsert failed: media=%s task=%s error=%s",
                payload.media.media_id,
                task.id,
                exc,
            )
        return CommandResult(task_id=task.id)

    def resolve_running_message(self) -> str:
        return "Creating download task"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Download task created"

    def resolve_failed_message(self) -> str:
        return "Failed to create download task"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.media.media_id)


class PilotEpisodeCommandHandler:
    command_type = CommandType.PILOT_EPISODE

    def _build_uniq_key(self, media_id, season_number: int | None = None) -> str:
        season_part = f":season={season_number}" if season_number is not None and season_number > 0 else ""
        return f"command:{CommandType.PILOT_EPISODE.value}:{media_id}{season_part}"

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        media = await media_service.resolve_execution_snapshot(
            request.target.media_id,
            season_number=request.target.season_number,
            require_tv_season=True,
            require_episode_count=True,
        )
        target_label = format_media_target_label(media)
        season_number = media.season_number
        payload = PilotEpisodeCommandRecordPayload(
            media=media,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.PILOT_EPISODE,
            payload=payload,
            initiator=body.initiator,
            media_id=media.media_id,
            target=MediaTarget(media_id=media.media_id, season_number=media.season_number),
            uniq_key=self._build_uniq_key(media.media_id, season_number),
            target_type=CommandTargetType.MEDIA,
            target_id=str(media.media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        task_count = await pilot_download_application_service.execute(
            media=payload.media,
            season_number=payload.media.season_number,
        )
        return CommandResult(result_count=task_count)

    def resolve_running_message(self) -> str:
        return "Running pilot download"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Pilot download submitted, created {result.result_count} download tasks"

    def resolve_failed_message(self) -> str:
        return "Pilot download failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.media.media_id)


class TaskTransferCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_TRANSFER

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskTransferCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_TRANSFER.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        result = await transfer_service.perform_transfer_by_task_id(payload.resolved_task_id)
        return CommandResult(transferred_files_count=len(result.transferred_files or []))

    def resolve_running_message(self) -> str:
        return "Transferring resource"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Transfer completed, processed {result.transferred_files_count} files"

    def resolve_failed_message(self) -> str:
        return "Resource transfer failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskStorageChangeCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_STORAGE_CHANGE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskStorageChangeCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
            target_downloader_id=request.target_downloader_id,
            target_directory_id=request.target_directory_id,
            cleanup_source_torrent=request.cleanup_source_torrent,
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_STORAGE_CHANGE.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        preview = await download_service.change_task_downloader(
            payload.resolved_task_id,
            request=TaskDownloaderChangeRequest(
                target_downloader_id=payload.target_downloader_id,
                target_directory_id=payload.target_directory_id,
                cleanup_source_torrent=payload.cleanup_source_torrent,
            ),
        )
        if not preview.ok:
            raise SystemException(message_key="backendErrors.taskStorageChangeBlocked", params={"reason": ",".join(preview.blockers)})
        return CommandResult(task_id=payload.resolved_task_id)

    def resolve_running_message(self) -> str:
        return "Starting storage change"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Storage change started"

    def resolve_failed_message(self) -> str:
        return "Storage change failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskMediaServerSyncCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_MEDIA_SERVER_SYNC

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskMediaServerSyncCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_MEDIA_SERVER_SYNC.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        count = await media_server_sync_service.rerun_for_task(
            payload.resolved_task_id,
            season_number=payload.target.season_number,
        )
        return CommandResult(result_count=count)

    def resolve_running_message(self) -> str:
        return "Rescraping media server metadata"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Scraping completed, processed {result.result_count} files"

    def resolve_failed_message(self) -> str:
        return "Scraping failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskDanmuGenerateCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_DANMU_GENERATE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskDanmuGenerateCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_DANMU_GENERATE.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        count = await danmu_application_service.run_for_task(payload.resolved_task_id)
        return CommandResult(result_count=count)

    def resolve_running_message(self) -> str:
        return "Regenerating danmu"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Danmu generation completed, processed {result.result_count} files"

    def resolve_failed_message(self) -> str:
        return "Danmu generation failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskPauseCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_PAUSE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskPauseCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_PAUSE.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        results = await download_service.pause_tasks([payload.resolved_task_id])
        if payload.resolved_task_id not in results or not results[payload.resolved_task_id]:
            raise SystemException()
        return CommandResult(task_id=payload.resolved_task_id)

    def resolve_running_message(self) -> str:
        return "Pausing task"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Task paused"

    def resolve_failed_message(self) -> str:
        return "Failed to pause task"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskResumeCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_RESUME

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskResumeCommandRecordPayload(
            resolved_task_id=task.id,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=f"command:{CommandType.TASK_RESUME.value}:{task.id}",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        results = await download_service.resume_tasks([payload.resolved_task_id])
        if payload.resolved_task_id not in results or not results[payload.resolved_task_id]:
            raise SystemException()
        return CommandResult(task_id=payload.resolved_task_id)

    def resolve_running_message(self) -> str:
        return "Resuming task"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Task resumed"

    def resolve_failed_message(self) -> str:
        return "Failed to resume task"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)


class TaskDeleteCommandHandler(TaskCommandSupport):
    command_type = CommandType.TASK_DELETE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        task = await self._resolve_task(request.task_id)
        payload = TaskDeleteCommandRecordPayload(
            resolved_task_id=task.id,
            delete_files=request.delete_files,
            force=request.force,
            delete_library_files=request.delete_library_files,
            delete_task=request.delete_task,
            target=_task_media_target(task),
        )
        return self._build_task_command_record(
            body=body,
            task=task,
            payload=payload,
            uniq_key=(
                f"command:{CommandType.TASK_DELETE.value}:{task.id}:"
                f"delete_files={int(request.delete_files)}:"
                f"force={int(request.force)}:"
                f"delete_library_files={int(request.delete_library_files)}:"
                f"delete_task={int(request.delete_task)}"
            ),
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        deleted_library_files_count = 0
        deleted_task = False
        if payload.delete_task or payload.delete_library_files:
            deleted_library_files_count, deleted_task = await download_service.delete_task_with_cleanup(
                payload.resolved_task_id,
                delete_files=payload.delete_files,
                force=payload.force,
                delete_library_files=payload.delete_library_files,
            )
        return CommandResult(
            deleted_library_files_count=deleted_library_files_count,
            deleted_task=bool(deleted_task),
        )

    def resolve_running_message(self) -> str:
        return "Deleting task"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Task deleted"

    def resolve_failed_message(self) -> str:
        return "Failed to delete task"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return self._resolve_task_action_context(command)

def register_download_command_handlers(registry) -> None:
    registry.register(TaskCreateCommandHandler())
    registry.register(PilotEpisodeCommandHandler())
    registry.register(TaskPauseCommandHandler())
    registry.register(TaskResumeCommandHandler())
    registry.register(TaskTransferCommandHandler())
    registry.register(TaskStorageChangeCommandHandler())
    registry.register(TaskMediaServerSyncCommandHandler())
    registry.register(TaskDanmuGenerateCommandHandler())
    registry.register(TaskDeleteCommandHandler())
