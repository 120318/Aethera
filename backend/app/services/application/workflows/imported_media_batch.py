import stat
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from app.schemas.domain.addon_events import ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.library import LibraryFile
from app.utils.fs_utils import fs_provider
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file


class CurrentImportedMediaBatch(BaseModel):
    imported_files: list[ImportedMediaFile]
    library_files_by_path: dict[str, LibraryFile]


def resolve_current_imported_media_batch(
    meta: MediaImportCompletedEventMeta,
    library_files: list[LibraryFile],
) -> CurrentImportedMediaBatch:
    library_files_by_path = {
        str(build_library_file_path(item.path, item.file_name)): item
        for item in library_files
        if item.id and file_name_looks_like_media_file(item.file_name or "")
    }
    event_files = meta.imported_files or (
        [ImportedMediaFile(destination_path=meta.file_path, episode_number=None)]
        if meta.file_path
        else []
    )
    return CurrentImportedMediaBatch(
        imported_files=[
            item
            for item in event_files
            if item.destination_path in library_files_by_path
        ],
        library_files_by_path=library_files_by_path,
    )


def ensure_current_imported_media_accessible(batch: CurrentImportedMediaBatch) -> None:
    ensure_imported_media_paths_accessible(item.destination_path for item in batch.imported_files)


def ensure_imported_media_paths_accessible(destination_paths: Iterable[str]) -> None:
    for destination_path in set(destination_paths):
        path = Path(destination_path)
        try:
            file_stat = fs_provider.file_stat(path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Imported library file is temporarily inaccessible: {path}") from exc
        except OSError as exc:
            raise OSError(f"Imported library file is temporarily inaccessible: {path}") from exc
        if not stat.S_ISREG(file_stat.st_mode):
            raise FileNotFoundError(f"Imported library file is temporarily inaccessible: {path}")
