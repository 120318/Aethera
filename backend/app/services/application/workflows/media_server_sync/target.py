import os
import re
from pathlib import Path

from app.schemas.domain.library import LibraryMediaLayout
from app.schemas.domain.library_layout import LibraryLayoutTargetFile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerSyncInput, MediaServerSyncTargetFile
from app.schemas.domain.media_types import MediaType
from app.services.domain.library.media_root_policy import library_media_root_policy


class MediaServerSyncTargetService:
    def build_input(self, media: MediaFullInfo, layout: LibraryMediaLayout) -> MediaServerSyncInput | None:
        decision = library_media_root_policy.build_from_library_layout(media, layout)
        if decision is None:
            return None
        return MediaServerSyncInput(
            anchor_file=decision.anchor_file,
            media_root_dir=decision.media_root_dir,
            transfer_results=[
                MediaServerSyncTargetFile(
                    destination_path=target.destination_path,
                    episode_number=target.episode_number,
                )
                for target in decision.target_files
            ],
            updated_paths=decision.updated_paths,
        )

    def resolve_media_root_dir(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
    ) -> Path:
        path = Path(file_path)
        if media.media_type == MediaType.movie:
            return self._infer_movie_dir(media, path, transfer_results or [])
        return self._infer_show_dir(media, path, transfer_results or [])

    def resolve_media_root_dir_from_targets(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile],
        fallback_media_root_dir: str | None,
    ) -> str | None:
        if not transfer_results:
            return fallback_media_root_dir
        decision = library_media_root_policy.build_from_target_files(
            media,
            [
                LibraryLayoutTargetFile(
                    destination_path=item.destination_path,
                    episode_number=item.episode_number,
                )
                for item in transfer_results
            ],
            anchor_file=file_path or None,
        )
        return (decision.media_root_dir if decision else None) or fallback_media_root_dir

    def get_season_dir_and_number(self, dest_path: Path, media: MediaFullInfo) -> tuple[Path | None, int | None]:
        season_dir = dest_path.parent if dest_path else None
        if not season_dir:
            return None, None
        root = self._disc_media_root(dest_path)
        if root:
            if root.name.lower().startswith("disc ") and root.parent != root:
                season_dir = root.parent
            elif root.name.lower().startswith("season "):
                season_dir = root
        season_num, _ = self._parse_season_episode_from_filename(dest_path)
        if season_num is None:
            season_num = media.season_number
        if season_num is None:
            return season_dir, None
        return season_dir, int(season_num)

    def is_video_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts", ".iso", ".bdmv", ".ifo", ".vob"}

    def build_target_files(
        self,
        transfer_results: list[MediaServerSyncTargetFile] | None,
    ) -> list[LibraryLayoutTargetFile]:
        return [
            LibraryLayoutTargetFile(
                destination_path=item.destination_path,
                episode_number=item.episode_number,
            )
            for item in (transfer_results or [])
        ]

    def _disc_media_root(self, path: Path) -> Path | None:
        upper_parts = [part.upper() for part in path.parts]
        for marker in ("BDMV", "VIDEO_TS"):
            if marker in upper_parts:
                index = upper_parts.index(marker)
                if index > 0:
                    return Path(*path.parts[:index])
        return None

    def _infer_show_dir_from_disc_root(self, media: MediaFullInfo, root: Path) -> Path:
        current = root
        while current.name.lower().startswith("disc ") and current.parent != current:
            current = current.parent
        if current.name.lower().startswith("season ") and current.parent != current:
            return current.parent
        if media.season_number is not None and current.parent.name.lower().startswith("season "):
            return current.parent.parent
        return current

    def _dir_contains_video_files(self, path: Path) -> bool:
        try:
            for item in path.iterdir():
                if self.is_video_file(item):
                    return True
        except OSError:
            return False
        return False

    def _infer_show_dir(self, media: MediaFullInfo, path: Path, targets: list[MediaServerSyncTargetFile]) -> Path:
        root = self._disc_media_root(path)
        if root:
            return self._infer_show_dir_from_disc_root(media, root)
        candidate_dirs = [str(Path(target.destination_path).parent) for target in targets or []]
        base_dir = Path(os.path.commonpath(candidate_dirs)) if candidate_dirs else path.parent
        root = self._disc_media_root(base_dir)
        if root:
            return self._infer_show_dir_from_disc_root(media, root)

        if self._is_season_dir(base_dir):
            return base_dir.parent

        if (base_dir / "tvshow.nfo").exists():
            return base_dir
        if (base_dir.parent / "tvshow.nfo").exists():
            return base_dir.parent

        parent = base_dir.parent
        if parent and parent.exists() and base_dir.exists() and self._dir_contains_video_files(base_dir) and not self._dir_contains_video_files(parent):
            video_dirs = []
            try:
                for item in parent.iterdir():
                    if item.is_dir() and self._dir_contains_video_files(item):
                        video_dirs.append(item)
            except OSError:
                video_dirs = []
            if len(video_dirs) == 1 and video_dirs[0] == base_dir and self._norm_title(base_dir.name) != self._norm_title(media.title):
                return parent

        return base_dir

    def _infer_movie_dir(self, media: MediaFullInfo, path: Path, targets: list[MediaServerSyncTargetFile]) -> Path:
        root = self._disc_media_root(path)
        if root:
            return self._infer_movie_dir_from_disc_root(media, root)
        candidate_dirs: list[Path] = []
        for target in targets or []:
            target_path = Path(target.destination_path)
            root = self._disc_media_root(target_path)
            if root:
                candidate_dirs.append(self._infer_movie_dir_from_disc_root(media, root))
                continue
            if self.is_video_file(target_path):
                candidate_dirs.append(target_path.parent)

        if self.is_video_file(path):
            return path.parent
        for candidate_dir in candidate_dirs:
            if candidate_dir == path.parent:
                return candidate_dir
        return candidate_dirs[0] if candidate_dirs else path.parent

    def _infer_movie_dir_from_disc_root(self, media: MediaFullInfo, root: Path) -> Path:
        parent = root.parent
        if parent != root and self._norm_title(media.title) and self._norm_title(media.title) in self._norm_title(parent.name):
            return parent
        return root

    def _parse_season_episode_from_filename(self, dest_path: Path) -> tuple[int | None, int | None]:
        name = dest_path.stem or ""
        matched = re.search(r"[Ss](\d{1,2})[Ee](\d{1,3})", name)
        if matched:
            return int(matched.group(1)), int(matched.group(2))
        matched = re.search(r"(\d{1,2})x(\d{1,3})", name)
        if matched:
            return int(matched.group(1)), int(matched.group(2))
        return None, None

    def _norm_title(self, value: str) -> str:
        return "".join(char for char in value.lower() if char.isalnum()) if value else ""

    def _is_season_dir(self, path: Path) -> bool:
        return path.name.lower().startswith("season ") and path.parent != path


media_server_sync_target = MediaServerSyncTargetService()
