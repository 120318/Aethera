from fastapi import APIRouter

from app.services.application.workflows.directory_migration import (
    DirectoryMigrationPreview,
    DirectoryMigrationRequest,
    directory_migration_service,
)

router = APIRouter()


@router.post("/config/directories/{directory_id}/migration/preview", response_model=DirectoryMigrationPreview)
async def preview_directory_migration(
    directory_id: str,
    body: DirectoryMigrationRequest,
) -> DirectoryMigrationPreview:
    return await directory_migration_service.preview(directory_id, body)
