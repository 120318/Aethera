from fastapi import APIRouter

from app.services.application.workflows.directory_migration import (
    DirectoryMigrationRequest,
    DirectoryMigrationSubmitResult,
    directory_migration_service,
)

router = APIRouter()


@router.post("/config/directories/{directory_id}/migration", response_model=DirectoryMigrationSubmitResult)
async def submit_directory_migration(
    directory_id: str,
    body: DirectoryMigrationRequest,
) -> DirectoryMigrationSubmitResult:
    return await directory_migration_service.submit(directory_id, body)
