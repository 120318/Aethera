import hashlib
import logging
import os
import shutil
from pathlib import Path

from app.core.storage_paths import get_library_root
from app.schemas.domain.library import LibraryFile, LibrarySidecarSnapshot
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
        candidate_dirs = self._delete_files(files, set())
        self.cleanup_directories_without_media_files(candidate_dirs)

    def delete_replaced_files(self, files: list[LibraryFile], preserved_paths: set[Path]) -> None:
        self._delete_files(files, preserved_paths)

    def _delete_files(self, files: list[LibraryFile], preserved_paths: set[Path]) -> list[Path]:
        candidate_dirs: list[Path] = []
        for item in files:
            try:
                full_path = build_library_file_path(item.path, item.file_name)
                candidate_dirs.append(full_path.parent)
                if full_path and full_path.exists() and full_path.is_file():
                    os.remove(str(full_path))
                    logger.debug("Physically removed library file: %s", full_path)
                self.delete_sidecar_files(full_path, preserved_paths)
            except OSError as exc:
                logger.warning("Failed to remove file %s: %s", item.path, exc)
        return candidate_dirs

    def delete_sidecar_files(self, media_file: Path, preserved_paths: set[Path]) -> None:
        if not media_file or not media_file.name:
            return
        for sidecar in self.sidecar_paths(media_file):
            if sidecar in preserved_paths:
                continue
            try:
                if sidecar.exists() and sidecar.is_file():
                    os.remove(str(sidecar))
                    logger.debug("Physically removed library sidecar file: %s", sidecar)
            except OSError as exc:
                logger.warning("Failed to remove sidecar file %s: %s", sidecar, exc)

    @staticmethod
    def sidecar_paths(media_file: Path) -> set[Path]:
        return {
            media_file.with_suffix(suffix)
            for suffix in LIBRARY_SIDECAR_EXTENSIONS
            if media_file.with_suffix(suffix) != media_file
        }

    def snapshot_sidecar_files(
        self,
        media_paths: set[Path],
        preserved_paths: set[Path],
    ) -> list[LibrarySidecarSnapshot]:
        snapshots: list[LibrarySidecarSnapshot] = []
        for media_path in sorted(media_paths):
            for sidecar in self.sidecar_paths(media_path):
                if sidecar in preserved_paths:
                    continue
                try:
                    if not sidecar.is_file():
                        continue
                    stat = sidecar.stat()
                    snapshots.append(LibrarySidecarSnapshot(
                        media_path=str(media_path),
                        sidecar_path=str(sidecar),
                        size=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                        inode=stat.st_ino,
                        content_digest=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                    ))
                except OSError as exc:
                    logger.warning("Failed to inspect library sidecar file %s: %s", sidecar, exc)
        return snapshots

    def delete_unchanged_sidecar_files(
        self,
        snapshots: list[LibrarySidecarSnapshot],
        replaced_media_paths: set[Path],
    ) -> None:
        for snapshot in snapshots:
            if Path(snapshot.media_path) not in replaced_media_paths:
                continue
            sidecar = Path(snapshot.sidecar_path)
            try:
                stat = sidecar.stat()
                if (
                    stat.st_size != snapshot.size
                    or stat.st_mtime_ns != snapshot.modified_ns
                    or stat.st_ino != snapshot.inode
                    or hashlib.sha256(sidecar.read_bytes()).hexdigest() != snapshot.content_digest
                ):
                    continue
                sidecar.unlink()
                logger.debug("Physically removed stale library sidecar file: %s", sidecar)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("Failed to remove stale library sidecar file %s: %s", sidecar, exc)

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
