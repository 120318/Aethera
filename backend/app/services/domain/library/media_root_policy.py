from __future__ import annotations

import os
from pathlib import Path

from app.schemas.domain.library import LibraryMediaLayout
from app.schemas.domain.library_layout import LibraryLayoutDecision, LibraryLayoutTargetFile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType


class LibraryMediaRootPolicy:
    def build_from_library_layout(
        self,
        media: MediaFullInfo,
        layout: LibraryMediaLayout,
    ) -> LibraryLayoutDecision | None:
        video_entries = [entry for entry in layout.entries if entry.is_video]
        if not video_entries:
            return None

        anchor_file = layout.primary_anchor_file or video_entries[0].absolute_path
        target_files: list[LibraryLayoutTargetFile] = []

        if media.media_type == MediaType.movie:
            target_files = [
                LibraryLayoutTargetFile(destination_path=entry.absolute_path)
                for entry in video_entries
            ]
        else:
            for entry in video_entries:
                episode_numbers = entry.episode_numbers or [None]
                for episode_number in episode_numbers:
                    target_files.append(
                        LibraryLayoutTargetFile(
                            destination_path=entry.absolute_path,
                            episode_number=episode_number,
                        )
                    )

        return self.build_from_target_files(media, target_files, anchor_file=anchor_file)

    def build_from_target_files(
        self,
        media: MediaFullInfo,
        target_files: list[LibraryLayoutTargetFile],
        *,
        anchor_file: str | None = None,
    ) -> LibraryLayoutDecision | None:
        if not target_files:
            return None

        resolved_anchor_file = anchor_file or target_files[0].destination_path
        anchor_path = Path(resolved_anchor_file)
        media_root_dir = self.get_media_root_dir(media, anchor_path, target_files)

        return LibraryLayoutDecision(
            anchor_file=resolved_anchor_file,
            media_root_dir=str(media_root_dir),
            updated_paths=[str(media_root_dir)],
            target_files=target_files,
        )

    def get_media_root_dir(
        self,
        media: MediaFullInfo,
        anchor_path: Path,
        target_files: list[LibraryLayoutTargetFile],
    ) -> Path:
        if media.media_type == MediaType.movie:
            return self.infer_movie_dir(media, anchor_path, target_files)
        return self.infer_show_dir(media, anchor_path, target_files)

    def infer_show_dir(
        self,
        media: MediaFullInfo,
        anchor_path: Path,
        target_files: list[LibraryLayoutTargetFile],
    ) -> Path:
        disc_root = self._disc_media_root(anchor_path)
        if disc_root:
            return self._infer_show_dir_from_disc_root(media, disc_root)
        candidate_dirs = [str(Path(item.destination_path).parent) for item in target_files]
        base_dir = Path(os.path.commonpath(candidate_dirs)) if candidate_dirs else anchor_path.parent
        disc_root = self._disc_media_root(base_dir)
        if disc_root:
            return self._infer_show_dir_from_disc_root(media, disc_root)

        if self._is_season_dir(base_dir):
            return base_dir.parent

        if (base_dir / "tvshow.nfo").exists():
            return base_dir
        if (base_dir.parent / "tvshow.nfo").exists():
            return base_dir.parent

        parent = base_dir.parent
        if parent and parent.exists() and base_dir.exists() and self._dir_contains_video_files(base_dir) and not self._dir_contains_video_files(parent):
            video_dirs: list[Path] = []
            try:
                for item in parent.iterdir():
                    if item.is_dir() and self._dir_contains_video_files(item):
                        video_dirs.append(item)
            except OSError:
                video_dirs = []

            if len(video_dirs) == 1 and video_dirs[0] == base_dir and self._normalize_title(base_dir.name) != self._normalize_title(media.title):
                return parent

        return base_dir

    def _infer_show_dir_from_disc_root(self, media: MediaFullInfo, disc_root: Path) -> Path:
        current = disc_root
        while current.name.lower().startswith("disc ") and current.parent != current:
            current = current.parent
        if current.name.lower().startswith("season ") and current.parent != current:
            return current.parent
        if media.season_number is not None and current.parent.name.lower().startswith("season "):
            return current.parent.parent
        return current

    def infer_movie_dir(
        self,
        media: MediaFullInfo,
        anchor_path: Path,
        target_files: list[LibraryLayoutTargetFile],
    ) -> Path:
        disc_root = self._disc_media_root(anchor_path)
        if disc_root:
            return self._infer_movie_dir_from_disc_root(media, disc_root)
        candidate_dirs: list[Path] = []
        for item in target_files:
            target_path = Path(item.destination_path)
            disc_root = self._disc_media_root(target_path)
            if disc_root:
                candidate_dirs.append(self._infer_movie_dir_from_disc_root(media, disc_root))
                continue
            if self._is_video_file(target_path):
                candidate_dirs.append(target_path.parent)

        if self._is_video_file(anchor_path):
            return anchor_path.parent

        for candidate_dir in candidate_dirs:
            if candidate_dir == anchor_path.parent:
                return candidate_dir

        return candidate_dirs[0] if candidate_dirs else anchor_path.parent

    def _infer_movie_dir_from_disc_root(self, media: MediaFullInfo, disc_root: Path) -> Path:
        parent = disc_root.parent
        if parent != disc_root and self._normalize_title(media.title) and self._normalize_title(media.title) in self._normalize_title(parent.name):
            return parent
        return disc_root

    def _is_video_file(self, path: Path) -> bool:
        return path.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".webm", ".m2ts", ".iso", ".bdmv", ".ifo", ".vob"}

    def _disc_media_root(self, path: Path) -> Path | None:
        upper_parts = [part.upper() for part in path.parts]
        for marker in ("BDMV", "VIDEO_TS"):
            if marker in upper_parts:
                index = upper_parts.index(marker)
                if index > 0:
                    return Path(*path.parts[:index])
        return None

    def _dir_contains_video_files(self, path: Path) -> bool:
        try:
            for item in path.iterdir():
                if item.is_file() and self._is_video_file(item):
                    return True
        except OSError:
            return False
        return False

    def _normalize_title(self, value: str | None) -> str:
        return "".join(ch.lower() for ch in (value or "") if ch.isalnum())

    def _is_season_dir(self, path: Path) -> bool:
        return path.name.lower().startswith("season ") and path.parent != path


library_media_root_policy = LibraryMediaRootPolicy()
