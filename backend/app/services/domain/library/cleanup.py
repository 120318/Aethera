import logging
import os
import shutil
from pathlib import Path

from app.core.storage_paths import get_library_root
from app.schemas.domain.library import LibraryFile
from app.services.domain.directory import directory_service
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file

logger = logging.getLogger("app.services.library.cleanup")

LIBRARY_SIDECAR_EXTENSIONS = {
    ".danmu.ass",
    ".danmu.xml",
    ".nfo",
}


class LibraryCleanup:
    def delete_files(self, files: list[LibraryFile]) -> None:
        candidate_dirs: list[Path] = []
        for item in files:
            try:
                full_path = build_library_file_path(item.path, item.file_name)
                candidate_dirs.append(full_path.parent)
                if full_path and full_path.exists() and full_path.is_file():
                    os.remove(str(full_path))
                    logger.debug("Physically removed library file: %s", full_path)
                self.delete_sidecar_files(full_path)
            except OSError as exc:
                logger.warning("Failed to remove file %s: %s", item.path, exc)
        self.cleanup_directories_without_media_files(candidate_dirs)

    def delete_sidecar_files(self, media_file: Path) -> None:
        if not media_file or not media_file.name:
            return
        for suffix in LIBRARY_SIDECAR_EXTENSIONS:
            sidecar = media_file.with_suffix(suffix)
            if sidecar == media_file:
                continue
            try:
                if sidecar.exists() and sidecar.is_file():
                    os.remove(str(sidecar))
                    logger.debug("Physically removed library sidecar file: %s", sidecar)
            except OSError as exc:
                logger.warning("Failed to remove sidecar file %s: %s", sidecar, exc)

    def cleanup_directories_without_media_files(self, directories: list[Path]) -> None:
        library_root = get_library_root().resolve()
        protected_roots = self.get_protected_library_roots(library_root)
        unique_dirs = sorted(
            {directory.resolve() for directory in directories if directory},
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in unique_dirs:
            boundary = self.resolve_directory_cleanup_boundary(directory, library_root, protected_roots)
            self.prune_directory_chain_without_media_files(directory, boundary)

    def get_protected_library_roots(self, library_root: Path) -> list[Path]:
        protected_roots: set[Path] = set(directory_service.list_library_cleanup_roots())
        protected_roots.add(library_root)
        return sorted(protected_roots, key=lambda path: len(path.parts), reverse=True)

    def resolve_directory_cleanup_boundary(
        self,
        directory: Path,
        library_root: Path,
        protected_roots: list[Path],
    ) -> Path:
        for protected_root in protected_roots:
            if directory == protected_root or self.is_under_root(directory, protected_root):
                return protected_root

        if self.is_under_root(directory, library_root):
            relative_parts = directory.relative_to(library_root).parts
            if relative_parts:
                return library_root / relative_parts[0]
            return library_root

        return directory

    def prune_directory_chain_without_media_files(self, start_directory: Path, boundary: Path) -> None:
        current = start_directory
        while current != boundary:
            if not current.exists() or not current.is_dir():
                current = current.parent
                continue
            if self.directory_contains_media_files(current):
                break
            try:
                shutil.rmtree(current)
                logger.debug("Removed library directory without media files: %s", current)
            except OSError as exc:
                logger.warning("Failed to remove library directory %s: %s", current, exc)
                break
            parent = current.parent
            if parent == current:
                break
            current = parent

    def directory_contains_media_files(self, directory: Path) -> bool:
        try:
            for child in directory.rglob("*"):
                if child.is_file() and file_name_looks_like_media_file(child.name):
                    return True
        except OSError as exc:
            logger.warning("Failed to inspect library directory %s: %s", directory, exc)
            return True
        return False

    @staticmethod
    def is_under_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
