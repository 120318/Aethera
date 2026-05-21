import asyncio
from dataclasses import dataclass
from typing import Mapping

from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_artifact_repository import LibraryFileArtifactRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.library_meta_repository import LibraryMetaRepository
from app.db.repositories.library_replace_repository import LibraryReplaceRepository
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import LibraryFileMissingEventMeta
from app.schemas.domain.download import TaskData, TransferFileResult
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.library import (
    LibraryFileArtifact,
    LibraryFileArtifactStatus,
    LibraryFileArtifactType,
    LibraryEpisode,
    LibraryFile,
    LibraryMediaLayout,
    LibraryPackageSummary,
    LibraryTaskFileHealth,
)
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.services.audit.event_service import event_service
from app.services.domain.library.cleanup import LibraryCleanup
from app.services.domain.library.deletion import LibraryDeletionWorker
from app.services.domain.library.layout import LibraryLayoutWorker
from app.services.domain.library.package_resources import find_package_for_file
from app.services.domain.library.package_resources import (
    build_library_package_summaries,
    is_displayable_library_file,
    matches_package_root,
    resolve_package_root,
)
from app.services.domain.library.registration import LibraryRegistrationWorker
from app.utils.library_paths import build_library_file_path, file_name_looks_like_media_file


@dataclass(frozen=True)
class MediaLibrarySnapshot:
    files: list[LibraryFile]
    present_episodes: set[int]


class LibraryService:
    def __init__(
        self,
        *,
        file_repo: LibraryFileRepository | None = None,
        artifact_repo: LibraryFileArtifactRepository | None = None,
        episode_repo: LibraryEpisodeRepository | None = None,
        meta_repo: LibraryMetaRepository | None = None,
        replace_repo: LibraryReplaceRepository | None = None,
        cleanup: LibraryCleanup | None = None,
    ) -> None:
        self._file_repo = file_repo or LibraryFileRepository()
        self._artifact_repo = artifact_repo or LibraryFileArtifactRepository()
        self._episode_repo = episode_repo or LibraryEpisodeRepository()
        self._meta_repo = meta_repo or LibraryMetaRepository()
        self._replace_repo = replace_repo or LibraryReplaceRepository()
        self._cleanup = cleanup or LibraryCleanup()
        self._registration = LibraryRegistrationWorker(
            file_repo=self._file_repo,
            episode_repo=self._episode_repo,
            meta_repo=self._meta_repo,
            replace_repo=self._replace_repo,
        )
        self._layout = LibraryLayoutWorker(self)
        self._deletion = LibraryDeletionWorker(
            query=self,
            file_repo=self._file_repo,
            artifact_repo=self._artifact_repo,
            episode_repo=self._episode_repo,
            meta_repo=self._meta_repo,
            cleanup=self._cleanup,
        )

    # Queries
    async def get_files_by_task(self, task_id: str) -> list[LibraryFile]:
        return await self._file_repo.find_by_task_id(task_id)

    async def update_file_location(self, file_id: str, *, directory_id: str, path: str, file_name: str) -> bool:
        return await self._file_repo.update_location(file_id, directory_id=directory_id, path=path, file_name=file_name)

    async def get_files_by_tasks(self, task_ids: list[str]) -> dict[str, list[LibraryFile]]:
        files = await self._file_repo.find_by_task_ids(task_ids)
        grouped: dict[str, list[LibraryFile]] = {task_id: [] for task_id in task_ids if task_id}
        for file in files:
            if not file.task_id:
                continue
            grouped.setdefault(file.task_id, []).append(file)
        return grouped

    async def has_task_entries(self, task_id: str) -> bool:
        return bool(await self._file_repo.find_by_task_id(task_id))

    async def count_task_primary_files(self, task_id: str) -> int:
        library_files = await self.get_files_by_task(task_id)
        return sum(1 for library_file in library_files if self.is_primary_file(library_file))

    async def find_file_by_id(self, file_id: str) -> LibraryFile | None:
        return await self._file_repo.find_one_by_id(file_id)

    async def get_artifacts_by_file_ids(self, file_ids: list[str]) -> list[LibraryFileArtifact]:
        return await self._artifact_repo.find_by_library_file_ids(file_ids)

    async def find_file_by_path(self, full_path: str) -> LibraryFile | None:
        return await self._file_repo.find_by_path(full_path)

    async def find_package_for_file(self, file: LibraryFile) -> LibraryPackageSummary | None:
        media_files = await self.get_files_by_media(file.media_id)
        return find_package_for_file(file, media_files)

    def build_package_summaries(self, files: list[LibraryFile]) -> list[LibraryPackageSummary]:
        return build_library_package_summaries(files)

    def resolve_package_root(self, file: LibraryFile) -> str | None:
        return resolve_package_root(file)

    def matches_package_root(self, file: LibraryFile, package_root: str) -> bool:
        return matches_package_root(file, package_root)

    def is_displayable_file(self, file: LibraryFile) -> bool:
        return is_displayable_library_file(file)

    async def list_media_ids_with_content(self) -> list[MediaID]:
        files = await self._file_repo.get_all()
        media_ids = {file.media_id for file in files if file.media_id}
        return sorted(media_ids, key=str)

    async def list_media_ids_by_directory_ids(self, directory_ids: list[str]) -> list[MediaID]:
        return await self._file_repo.list_media_ids_by_directory_ids(directory_ids)

    async def list_files(self) -> list[LibraryFile]:
        return await self._file_repo.get_all()

    async def get_episodes_by_media(self, media_id: MediaID) -> list[LibraryEpisode]:
        return await self._episode_repo.find_by_media_id(media_id)

    async def get_files_by_media(self, media_id: MediaID, season: int | None = None) -> list[LibraryFile]:
        if season is None or media_id.media_type == MediaType.movie:
            return await self._file_repo.find_by_media_id(media_id)

        episodes = await self._episode_repo.find_by_media_and_season(media_id, int(season))
        episode_file_ids = {ep.file_id for ep in episodes if ep.file_id}
        files: list[LibraryFile] = []
        if episode_file_ids:
            files.extend(await self._file_repo.find_by_ids(list(episode_file_ids)))
        direct_files = await self._file_repo.find_by_media_id(media_id)
        files.extend(file for file in direct_files if self._is_original_disc_file_for_season(file, int(season)))
        return list({file.id: file for file in files}.values())

    async def get_media_library_snapshot(self, media_id: MediaID, season: int | None = None) -> MediaLibrarySnapshot:
        if media_id.media_type == MediaType.movie:
            return MediaLibrarySnapshot(
                files=await self._file_repo.find_by_media_id(media_id),
                present_episodes=set(),
            )
        if season is None:
            files, episodes = await asyncio.gather(
                self._file_repo.find_by_media_id(media_id),
                self._episode_repo.find_by_media_id(media_id),
            )
            return MediaLibrarySnapshot(
                files=files,
                present_episodes={episode.episode for episode in episodes},
            )

        season_value = int(season)
        episodes = await self._episode_repo.find_by_media_and_season(media_id, season_value)
        episode_file_ids = {episode.file_id for episode in episodes if episode.file_id}
        episode_files_task = self._file_repo.find_by_ids(list(episode_file_ids)) if episode_file_ids else self._empty_files()
        direct_files, episode_files = await asyncio.gather(
            self._file_repo.find_by_media_id(media_id),
            episode_files_task,
        )
        files = list(episode_files)
        files.extend(file for file in direct_files if self._is_original_disc_file_for_season(file, season_value))
        return MediaLibrarySnapshot(
            files=list({file.id: file for file in files}.values()),
            present_episodes={episode.episode for episode in episodes},
        )

    async def _empty_files(self) -> list[LibraryFile]:
        return []

    async def get_files_by_media_and_directory_ids(self, media_id: MediaID, directory_ids: list[str]) -> list[LibraryFile]:
        return await self._file_repo.find_by_media_id_and_directory_ids(media_id, directory_ids)

    async def get_present_episodes(self, media_id: MediaID, season: int | None = None) -> set[int]:
        if season is None:
            episodes = await self.get_episodes_by_media(media_id)
        else:
            episodes = await self._episode_repo.find_by_media_and_season(media_id, int(season))
        return {ep.episode for ep in episodes}

    async def get_episode_attributes(
        self,
        media_id: MediaID,
        season: int | None = None,
    ) -> Mapping[int, list[ResourceAttributes]]:
        if season is None:
            episodes = await self._episode_repo.find_by_media_id(media_id)
        else:
            episodes = await self._episode_repo.find_by_media_and_season(media_id, int(season))
        if not episodes:
            return {}

        file_ids = list({ep.file_id for ep in episodes if ep.file_id})
        files = await self._file_repo.find_by_ids(file_ids)
        file_map = {file.id: file.resource_attributes for file in files if file.id}
        out: dict[int, list[ResourceAttributes]] = {}
        for episode in episodes:
            attrs = file_map[episode.file_id] if episode.file_id in file_map else None
            if attrs:
                out.setdefault(int(episode.episode), []).append(attrs)
        return out

    # Layout and file predicates
    def file_exists(self, library_file: LibraryFile) -> bool:
        return self._layout.file_exists(library_file)

    def is_primary_file(self, library_file: LibraryFile) -> bool:
        return self._layout.is_primary_file(library_file)

    def build_file_exists_map(self, library_files: list[LibraryFile]) -> dict[str, bool]:
        return self._layout.build_file_exists_map(library_files)

    async def get_media_layout(self, media_id: MediaID) -> LibraryMediaLayout:
        return await self._layout.get_media_layout(media_id)

    async def get_media_layout_for_files(self, media_id: MediaID, files: list[LibraryFile]) -> LibraryMediaLayout:
        return await self._layout.build_media_layout(media_id, files)

    async def get_task_file_health(
        self,
        task_id: str,
        expected_total_count: int | None = None,
    ) -> LibraryTaskFileHealth:
        return await self._layout.get_task_file_health(task_id, expected_total_count=expected_total_count)

    async def reconcile_task_primary_files(
        self,
        task: TaskData,
        expected_total_count: int | None = None,
    ) -> LibraryTaskFileHealth:
        library_files = await self.get_files_by_task(task.id)
        primary_files = [library_file for library_file in library_files if self.is_primary_file(library_file)]
        missing_files = [library_file for library_file in primary_files if not self.file_exists(library_file)]
        existing_count = len(primary_files) - len(missing_files)
        expected_count = max(
            len(primary_files),
            expected_total_count or 0,
            self._expected_primary_count_from_task(task) or 0,
        )
        if missing_files:
            await self._record_missing_primary_files(task, missing_files)
            missing_file_ids = [library_file.id for library_file in missing_files if library_file.id]
            await self._artifact_repo.remove_by_library_file_ids(missing_file_ids)
            await self._episode_repo.remove_by_file_ids(missing_file_ids)
            await self._file_repo.remove_by_ids(missing_file_ids)
        return LibraryTaskFileHealth(
            total_primary_count=expected_count,
            existing_primary_count=existing_count,
        )

    def _expected_primary_count_from_task(self, task: TaskData) -> int | None:
        if not task.metadata or not task.metadata.files:
            return None
        selected = set(task.context.selected_files) if task.context and task.context.selected_files else None
        count = 0
        for index, item in enumerate(task.metadata.files):
            if selected is not None and index not in selected:
                continue
            if file_name_looks_like_media_file(item.filename.lower()):
                count += 1
        return count if count > 0 else None

    async def _record_missing_primary_files(self, task: TaskData, missing_files: list[LibraryFile]) -> None:
        media = task.context.media
        for library_file in missing_files:
            full_path = str(build_library_file_path(library_file.path, library_file.file_name))
            event_service.emit_media(
                MediaEventCreate(
                    type=EventTypes.LIBRARY_FILE_MISSING,
                    level=EventLevel.warning,
                    media=media,
                    task_id=task.id,
                    actor=EventActor.system,
                    source=EventSource.base,
                    entities=[
                        EventEntityRef(type="task", id=task.id),
                        EventEntityRef(type="media", id=str(task.media_id)),
                        EventEntityRef(type="library_file", id=library_file.id),
                    ],
                ),
                meta=LibraryFileMissingEventMeta(
                    task_id=task.id,
                    directory_id=library_file.directory_id,
                    media_id=library_file.media_id,
                    library_file_id=library_file.id,
                    path=full_path,
                ),
            )

    async def mark_artifact(
        self,
        *,
        library_file_id: str,
        artifact_type: LibraryFileArtifactType,
        expected_path: str,
        status: LibraryFileArtifactStatus,
        last_error: str | None = None,
    ) -> LibraryFileArtifact:
        return await self._artifact_repo.upsert_expected(
            library_file_id=library_file_id,
            artifact_type=artifact_type,
            expected_path=expected_path,
            status=status,
            last_error=last_error,
        )

    async def mark_artifacts_missing_by_paths(self, paths: list[str]) -> int:
        return await self._artifact_repo.mark_missing_by_paths(paths)

    # Registration
    async def upsert_media_entry(self, media_id: MediaID) -> None:
        await self._registration.upsert_media_entry(media_id)

    async def register_transfer_results(
        self,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_results: list[TransferFileResult],
        season: int | None = None,
    ) -> None:
        await self._registration.register_transfer_results(task_id, directory_id, media_id, transfer_results, season)

    async def replace_task_entries(
        self,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_results: list[TransferFileResult],
        season: int | None = None,
        replacement_files: list[LibraryFile] | None = None,
    ) -> list[LibraryFile]:
        return await self._registration.replace_task_entries(
            task_id,
            directory_id,
            media_id,
            transfer_results,
            season,
            replacement_files,
        )

    # Deletion
    async def delete_task_library_records(self, task_id: str) -> int:
        return await self._deletion.delete_task_library_records(task_id)

    async def delete_task_library_files(self, task_id: str, force: bool = False) -> int:
        return await self._deletion.delete_task_library_files(task_id, force=force)

    async def delete_file_by_id(self, file_id: str, force: bool = False) -> bool:
        return await self._deletion.delete_file_by_id(file_id, force=force)

    async def delete_media_library_files(
        self,
        media_id: MediaID,
        *,
        season: int | None = None,
        force: bool = False,
    ) -> int:
        return await self._deletion.delete_media_library_files(media_id, season=season, force=force)

    async def archive_media_entry(self, media_id: MediaID) -> None:
        await self._deletion.archive_media_entry(media_id)

    def _is_original_disc_file_for_season(self, file: LibraryFile, season: int) -> bool:
        attrs = file.resource_attributes
        if not attrs or not attrs.package_layout:
            return False
        if not attrs.seasons:
            return season == 1
        return season in attrs.seasons


library_service = LibraryService()
