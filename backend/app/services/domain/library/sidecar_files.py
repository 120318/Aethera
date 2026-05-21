from pathlib import Path

from app.utils.fs_utils import write_text_file


class LibrarySidecarFiles:
    def path_exists(self, path: Path | None) -> bool:
        if not path:
            return False
        return path.exists()

    def missing_paths(self, paths: list[Path | None]) -> list[str]:
        return [str(path) for path in paths if path and not self.path_exists(path)]

    def write_text_file(self, path: Path, content: str) -> None:
        write_text_file(path, content)


library_sidecar_files = LibrarySidecarFiles()
