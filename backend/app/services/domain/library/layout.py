from app.schemas.domain.library import LibraryFile, LibraryMediaLayout, LibraryMediaLayoutEntry, LibraryTaskFileHealth
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.domain.library.service_types import LibraryQueryProtocol
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file


class LibraryLayoutWorker:
    def __init__(self, query: LibraryQueryProtocol) -> None:
        self.query = query

    def file_exists(self, library_file: LibraryFile) -> bool:
        return build_library_file_path(library_file.path, library_file.file_name).exists()

    def is_primary_file(self, library_file: LibraryFile) -> bool:
        return file_name_looks_like_media_file((library_file.file_name or "").lower())

    def build_file_exists_map(self, library_files: list[LibraryFile]) -> dict[str, bool]:
        return {
            library_file.id: self.file_exists(library_file)
            for library_file in library_files
            if library_file.id
        }

    async def get_media_layout(self, media_id: MediaID) -> LibraryMediaLayout:
        files = await self.query.get_files_by_media(media_id)
        return await self.build_media_layout(media_id, files)

    async def build_media_layout(self, media_id: MediaID, files: list[LibraryFile]) -> LibraryMediaLayout:
        episodes = await self.query.get_episodes_by_media(media_id) if media_id.media_type == MediaType.tv else []
        file_episode_map: dict[str, list[int]] = {}
        for episode in episodes:
            file_episode_map.setdefault(str(episode.file_id), []).append(int(episode.episode))

        entries: list[LibraryMediaLayoutEntry] = []
        root_dirs: set[str] = set()
        video_entries: list[LibraryMediaLayoutEntry] = []
        for library_file in files:
            absolute_path = build_library_file_path(library_file.path, library_file.file_name)
            exists = absolute_path.exists()
            is_video = exists and self.is_primary_file(library_file)
            entry = LibraryMediaLayoutEntry(
                file_id=library_file.id,
                absolute_path=str(absolute_path),
                file_size=library_file.file_size,
                is_video=is_video,
                episode_numbers=sorted(file_episode_map[str(library_file.id)]) if str(library_file.id) in file_episode_map else [],
            )
            entries.append(entry)
            if exists:
                root_dirs.add(str(absolute_path.parent))
            if is_video:
                video_entries.append(entry)

        primary_anchor_file = self._resolve_primary_anchor(media_id, video_entries)
        return LibraryMediaLayout(
            media_id=media_id,
            media_type=media_id.media_type,
            entries=entries,
            root_dirs=sorted(root_dirs),
            primary_anchor_file=primary_anchor_file,
        )

    async def get_task_file_health(
        self,
        task_id: str,
        expected_total_count: int | None = None,
    ) -> LibraryTaskFileHealth:
        library_files = await self.query.get_files_by_task(task_id)
        primary_files = [library_file for library_file in library_files if self.is_primary_file(library_file)]
        existing_count = sum(1 for library_file in primary_files if self.file_exists(library_file))
        total_count = max(len(primary_files), expected_total_count or 0)
        return LibraryTaskFileHealth(
            total_primary_count=total_count,
            existing_primary_count=existing_count,
        )

    def _resolve_primary_anchor(self, media_id: MediaID, video_entries: list[LibraryMediaLayoutEntry]) -> str | None:
        if not video_entries:
            return None
        if media_id.media_type == MediaType.movie:
            return max(video_entries, key=lambda item: item.file_size or 0).absolute_path
        return sorted(video_entries, key=lambda item: item.absolute_path)[0].absolute_path
