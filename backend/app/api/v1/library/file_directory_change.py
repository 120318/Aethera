from fastapi import APIRouter
from pydantic import BaseModel

from app.services.domain.library.directory_change import (
    LibraryFileDirectoryChangePreview,
    LibraryFileDirectoryChangeRequest,
    library_file_directory_change_service,
)

router = APIRouter()


class LibraryFileDirectoryChangePreviewRequest(BaseModel):
    file_id: str
    target_directory_id: str
    package_root: str = ""


@router.post("/file/directory-change/preview", response_model=LibraryFileDirectoryChangePreview)
async def preview_library_file_directory_change(
    body: LibraryFileDirectoryChangePreviewRequest,
) -> LibraryFileDirectoryChangePreview:
    return await library_file_directory_change_service.preview(
        body.file_id,
        LibraryFileDirectoryChangeRequest(
            target_directory_id=body.target_directory_id,
            package_root=body.package_root,
        ),
    )
