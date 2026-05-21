from __future__ import annotations

import uuid

from app.schemas.exception.exceptions import InvalidRequestException, ResourceNotFoundException
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    LibraryFileDanmuGenerateCommandRecordPayload,
    LibraryFileDeleteCommandRecordPayload,
    LibraryFileMediaServerSyncCommandRecordPayload,
    LibraryFileStorageChangeCommandRecordPayload,
    MediaDeleteCommandRecordPayload,
)
from app.schemas.domain.library import LibraryFile
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.media_resource_deletion import media_resource_deletion_service
from app.services.application.workflows.media_server_sync.service import media_server_sync_service
from app.services.application.commands.target_labels import format_media_target_label
from app.services.domain.download import download_service
from app.services.domain.library.directory_change import (
    LibraryFileDirectoryChangeRequest,
    library_file_directory_change_service,
)
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service


class LibraryFileDeleteCommandHandler:
    command_type = CommandType.LIBRARY_FILE_DELETE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        library_file = await library_service.find_file_by_id(request.file_id)
        if not library_file:
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        target = request.target
        payload = LibraryFileDeleteCommandRecordPayload(
            file_id=library_file.id,
            target=target,
            force=request.force,
            package_root=request.package_root,
        )
        target_id = request.package_root or library_file.id
        target_label = request.package_root.split("/")[-1] if request.package_root else (library_file.file_name or library_file.id)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.LIBRARY_FILE_DELETE,
            payload=payload,
            initiator=body.initiator,
            media_id=target.media_id,
            target=target,
            uniq_key=(
                f"command:{CommandType.LIBRARY_FILE_DELETE.value}:{target_id}:"
                f"force={int(request.force)}"
            ),
            target_type=CommandTargetType.LIBRARY_FILE,
            target_id=target_id,
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        library_file = await library_service.find_file_by_id(payload.file_id)
        expected_total_count = 0
        task_id = library_file.task_id if library_file else None
        if task_id:
            expected_total_count = await library_service.count_task_primary_files(task_id)
        deleted_count = 0
        if payload.package_root:
            files = await library_service.get_files_by_media(payload.target.media_id)
            for item in files:
                if item.task_id == task_id and library_service.matches_package_root(item, payload.package_root):
                    await library_service.delete_file_by_id(item.id, force=payload.force)
                    deleted_count += 1
        else:
            await library_service.delete_file_by_id(payload.file_id, force=payload.force)
            deleted_count = 1
        if task_id and expected_total_count > 0:
            await download_service.refresh_completed_task_health(
                task_id,
                expected_total_count=expected_total_count,
            )
        return CommandResult(deleted_library_files_count=deleted_count)

    def resolve_running_message(self) -> str:
        return "Deleting file"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "File deleted"

    def resolve_failed_message(self) -> str:
        return "Failed to delete file"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


class _LibraryFileOperationMixin:
    def _target_id(self, request) -> str:
        return request.package_root or request.file_id

    def _target_label(self, library_file: LibraryFile, package_root: str) -> str:
        if package_root:
            return package_root.rstrip("/").rsplit("/", 1)[-1] or package_root
        return library_file.file_name or library_file.id

    async def _resolve_library_file(self, file_id: str) -> LibraryFile:
        library_file = await library_service.find_file_by_id(file_id)
        if not library_file:
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        return library_file

    async def _resolve_library_files(self, file_id: str, package_root: str) -> list[LibraryFile]:
        library_file = await self._resolve_library_file(file_id)
        if not package_root:
            return [library_file]
        files = await library_service.get_files_by_media(library_file.media_id)
        return [
            item
            for item in files
            if item.task_id == library_file.task_id and library_service.matches_package_root(item, package_root)
        ]


class LibraryFileMediaServerSyncCommandHandler(_LibraryFileOperationMixin):
    command_type = CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        library_file = await self._resolve_library_file(request.file_id)
        target_id = self._target_id(request)
        media = await media_service.resolve_execution_snapshot(
            request.target.media_id,
            season_number=request.target.season_number,
        )
        payload = LibraryFileMediaServerSyncCommandRecordPayload(
            file_id=library_file.id,
            target=request.target,
            package_root=request.package_root,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC,
            payload=payload,
            initiator=body.initiator,
            media_id=request.target.media_id,
            target=request.target,
            uniq_key=f"command:{CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC.value}:{target_id}",
            target_type=CommandTargetType.LIBRARY_FILE,
            target_id=target_id,
            target_label=format_media_target_label(media),
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        files = await self._resolve_library_files(payload.file_id, payload.package_root)
        count = await media_server_sync_service.rerun_for_library_files(
            files,
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
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


class LibraryFileStorageChangeCommandHandler(_LibraryFileOperationMixin):
    command_type = CommandType.LIBRARY_FILE_STORAGE_CHANGE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        library_file = await self._resolve_library_file(request.file_id)
        target_id = self._target_id(request)
        media = await media_service.resolve_execution_snapshot(
            request.target.media_id,
            season_number=request.target.season_number,
        )
        payload = LibraryFileStorageChangeCommandRecordPayload(
            file_id=library_file.id,
            target=request.target,
            target_directory_id=request.target_directory_id,
            package_root=request.package_root,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.LIBRARY_FILE_STORAGE_CHANGE,
            payload=payload,
            initiator=body.initiator,
            media_id=request.target.media_id,
            target=request.target,
            uniq_key=f"command:{CommandType.LIBRARY_FILE_STORAGE_CHANGE.value}:{target_id}:{request.target_directory_id}",
            target_type=CommandTargetType.LIBRARY_FILE,
            target_id=target_id,
            target_label=format_media_target_label(media),
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        preview = await library_file_directory_change_service.execute(
            payload.file_id,
            LibraryFileDirectoryChangeRequest(
                target_directory_id=payload.target_directory_id,
                package_root=payload.package_root,
            ),
        )
        if not preview.ok:
            raise InvalidRequestException(
                "backendErrors.libraryFileDirectoryChangeBlocked",
                params={"reason": ",".join(preview.blockers)},
            )
        return CommandResult(result_count=preview.file_count)

    def resolve_running_message(self) -> str:
        return "Changing library file directory"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Directory changed, processed {result.result_count} files"

    def resolve_failed_message(self) -> str:
        return "Failed to change library file directory"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


class LibraryFileDanmuGenerateCommandHandler(_LibraryFileOperationMixin):
    command_type = CommandType.LIBRARY_FILE_DANMU_GENERATE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        library_file = await self._resolve_library_file(request.file_id)
        target_id = self._target_id(request)
        media = await media_service.resolve_execution_snapshot(
            request.target.media_id,
            season_number=request.target.season_number,
        )
        payload = LibraryFileDanmuGenerateCommandRecordPayload(
            file_id=library_file.id,
            target=request.target,
            package_root=request.package_root,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.LIBRARY_FILE_DANMU_GENERATE,
            payload=payload,
            initiator=body.initiator,
            media_id=request.target.media_id,
            target=request.target,
            uniq_key=f"command:{CommandType.LIBRARY_FILE_DANMU_GENERATE.value}:{target_id}",
            target_type=CommandTargetType.LIBRARY_FILE,
            target_id=target_id,
            target_label=format_media_target_label(media),
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        files = await self._resolve_library_files(payload.file_id, payload.package_root)
        count = await danmu_application_service.run_for_library_files(files)
        return CommandResult(result_count=count)

    def resolve_running_message(self) -> str:
        return "Regenerating danmu"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Danmu generation completed, processed {result.result_count} files"

    def resolve_failed_message(self) -> str:
        return "Danmu generation failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


class MediaDeleteCommandHandler:
    command_type = CommandType.MEDIA_DELETE

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        target = request.target
        payload = MediaDeleteCommandRecordPayload(
            target=target,
            mode=request.mode,
            delete_files=request.delete_files,
            force=request.force,
        )
        media = await media_service.resolve_execution_snapshot(
            target.media_id,
            season_number=target.season_number,
        )
        target_label = format_media_target_label(media)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.MEDIA_DELETE,
            payload=payload,
            initiator=body.initiator,
            media_id=target.media_id,
            target=target,
            uniq_key=(
                f"command:{CommandType.MEDIA_DELETE.value}:{target.media_id}:"
                f"season={target.season_number or 'all'}:"
                f"mode={request.mode}:delete_files={int(request.delete_files)}:force={int(request.force)}"
            ),
            target_type=CommandTargetType.MEDIA,
            target_id=str(target.media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        deleted_tasks_count, deleted_library_files_count = await media_resource_deletion_service.delete_media_resources(
            payload.target.media_id,
            season_number=payload.target.season_number,
            mode=payload.mode,
            delete_files=payload.delete_files,
            force=payload.force,
        )

        return CommandResult(
            deleted_tasks_count=deleted_tasks_count,
            deleted_library_files_count=deleted_library_files_count,
        )

    def resolve_running_message(self) -> str:
        return "Deleting media resources"

    def resolve_success_message(self, result: CommandResult) -> str:
        return (
            f"Media resources deleted, removed {result.deleted_tasks_count} tasks and "
            f"{result.deleted_library_files_count} library files"
        )

    def resolve_failed_message(self) -> str:
        return "Failed to delete media resources"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


def register_library_command_handlers(registry) -> None:
    registry.register(LibraryFileDeleteCommandHandler())
    registry.register(LibraryFileStorageChangeCommandHandler())
    registry.register(LibraryFileMediaServerSyncCommandHandler())
    registry.register(LibraryFileDanmuGenerateCommandHandler())
    registry.register(MediaDeleteCommandHandler())
