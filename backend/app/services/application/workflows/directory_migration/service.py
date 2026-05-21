from __future__ import annotations

from pydantic import Field

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandType,
    TaskStorageChangeCommandRequestPayload,
)
from app.services.application.commands.service import command_service
from app.services.domain.directory.migration import (
    DirectoryMigrationPreview,
    DirectoryMigrationRequest,
    directory_migration_domain_service,
)
from app.services.config.settings_service import settings_service


class DirectoryMigrationSubmitResult(DirectoryMigrationPreview):
    commands: list[CommandRecord] = Field(default_factory=list)
    migrated_subscription_count: int = 0


class DirectoryMigrationService:
    async def preview(self, source_directory_id: str, request: DirectoryMigrationRequest) -> DirectoryMigrationPreview:
        return await directory_migration_domain_service.preview(source_directory_id, request)

    async def submit(self, source_directory_id: str, request: DirectoryMigrationRequest) -> DirectoryMigrationSubmitResult:
        preview = await self.preview(source_directory_id, request)
        result = DirectoryMigrationSubmitResult(**preview.model_dump(), commands=[], migrated_subscription_count=0)
        if not preview.ok:
            return result
        task_ids = await directory_migration_domain_service.migratable_task_ids(source_directory_id, preview)
        for task_id in task_ids:
            command = await command_service.create_command(
                CommandCreateRequest(
                    type=CommandType.TASK_STORAGE_CHANGE,
                    initiator=CommandInitiator.MANUAL,
                    payload=TaskStorageChangeCommandRequestPayload(
                        task_id=task_id,
                        target_downloader_id=preview.target_downloader_id,
                        target_directory_id=preview.target_directory_id,
                    ),
                )
            )
            result.commands.append(command)
        result.migrated_subscription_count = await directory_migration_domain_service.migrate_subscriptions(
            source_directory_id,
            preview.target_directory_id,
        )
        settings_service.migrate_directory_references(source_directory_id, preview.target_directory_id)
        return result


directory_migration_service = DirectoryMigrationService()
