import asyncio
import logging

from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_artifact_repository import LibraryFileArtifactRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.library_meta_repository import LibraryMetaRepository
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.addon_events import MediaDeletedEventMeta
from app.schemas.domain.event import EventActor, EventEntityRef, EventSource, MediaEventCreate
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import DownloadException
from app.schemas.media_id import MediaID
from app.services.audit.event_service import event_service
from app.services.domain.library.cleanup import LibraryCleanup
from app.services.domain.library.service_types import LibraryQueryProtocol
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.library_paths import build_library_file_path

logger = logging.getLogger("app.services.library")


class LibraryDeletionWorker:
    def __init__(
        self,
        *,
        query: LibraryQueryProtocol,
        file_repo: LibraryFileRepository,
        artifact_repo: LibraryFileArtifactRepository,
        episode_repo: LibraryEpisodeRepository,
        meta_repo: LibraryMetaRepository,
        cleanup: LibraryCleanup,
    ) -> None:
        self.query = query
        self.file_repo = file_repo
        self.artifact_repo = artifact_repo
        self.episode_repo = episode_repo
        self.meta_repo = meta_repo
        self.cleanup = cleanup

    @staticmethod
    def _positive_season_number(value: int | None) -> int | None:
        if value is None:
            return None
        number = int(value)
        return number if number > 0 else None

    def _library_files_season_number(self, files: list[LibraryFile]) -> int | None:
        seasons: set[int] = set()
        for file in files:
            attrs = file.resource_attributes
            if attrs is None:
                continue
            seasons.update(
                number
                for number in (self._positive_season_number(raw) for raw in attrs.seasons)
                if number is not None
            )
        return next(iter(seasons)) if len(seasons) == 1 else None

    async def delete_task_library_records(self, task_id: str) -> int:
        library_files = await self.file_repo.find_by_task_id(task_id)
        file_ids = [file.id for file in library_files if file.id]
        await self.artifact_repo.remove_by_library_file_ids(file_ids)
        episodes_deleted = await self.episode_repo.remove_by_file_ids(file_ids)
        files_deleted = await self.file_repo.remove_by_task_id(task_id)
        logger.debug(
            "Deleted %d library files and %d episodes for task %s",
            files_deleted,
            episodes_deleted,
            task_id,
        )
        return files_deleted

    async def delete_task_library_files(self, task_id: str, force: bool = False) -> int:
        files = await self.query.get_files_by_task(task_id)
        media_id = files[0].media_id if files else None
        delete_events = self._group_delete_event_files(files)
        if files:
            await asyncio.to_thread(self.cleanup.delete_files, files)
        try:
            deleted_count = await self.delete_task_library_records(task_id)
        except AppException:
            if force:
                return 0
            raise
        if media_id:
            for directory_id, event_files in delete_events.items():
                await self._emit_media_delete_event(
                    media_id,
                    [str(build_library_file_path(item.path, item.file_name)) for item in event_files if item.file_name],
                    directory_id=directory_id,
                    delete_scope="file",
                    season_number=self._library_files_season_number(event_files),
                )
        return deleted_count

    async def delete_file_by_id(self, file_id: str, force: bool = False) -> bool:
        async with domain_lock_service.acquire_library_file_op(file_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.fileBusy")

            library_file = await self.query.find_file_by_id(file_id)
            if not library_file:
                return True

            full_path = str(build_library_file_path(library_file.path, library_file.file_name))
            await asyncio.to_thread(self.cleanup.delete_files, [library_file])
            await self.episode_repo.remove_by_file_ids([library_file.id])
            await self.artifact_repo.remove_by_library_file_ids([library_file.id])
            await self.file_repo.remove_by_ids([library_file.id])
            await self._emit_media_delete_event(
                library_file.media_id,
                [full_path],
                directory_id=library_file.directory_id,
                delete_scope="file",
                season_number=self._library_files_season_number([library_file]),
            )
            return True

    async def delete_media_library_files(
        self,
        media_id: MediaID,
        *,
        force: bool = False,
        season: int | None = None,
    ) -> int:
        files = await self.query.get_files_by_media(media_id, season=season)
        file_ids = list({file.id for file in files if file.id})
        if not file_ids:
            return 0
        await self.artifact_repo.remove_by_library_file_ids(file_ids)
        delete_events = self._group_delete_event_files(files)
        media_roots = {
            directory_id: await self._resolve_media_root_dir_for_files(media_id, event_files)
            for directory_id, event_files in delete_events.items()
        }

        if files:
            try:
                await asyncio.to_thread(self.cleanup.delete_files, files)
            except OSError as exc:
                if not force:
                    raise
                logger.warning("Failed to physically delete some files for media %s: %s", media_id, exc)

        if media_id.media_type != MediaType.movie:
            await self.episode_repo.remove_by_file_ids(file_ids)
        deleted_count = await self.file_repo.remove_by_ids(file_ids)
        for directory_id, event_files in delete_events.items():
            deleted_paths = [
                str(build_library_file_path(item.path, item.file_name))
                for item in event_files
                if item.file_name
            ]
            media_root_dir = media_roots.get(directory_id)
            event_paths = [media_root_dir] if media_root_dir else deleted_paths
            await self._emit_media_delete_event(
                media_id,
                event_paths,
                directory_id=directory_id,
                delete_scope="media_root" if media_root_dir else "file",
                media_root_dir=media_root_dir,
                season_number=season or self._library_files_season_number(event_files),
            )
        return deleted_count

    async def archive_media_entry(self, media_id: MediaID) -> None:
        await self.meta_repo.archive_by_media_id(media_id)

    async def _resolve_media_root_dir(self, media_id: MediaID) -> str | None:
        from app.services.domain.library.media_root_policy import library_media_root_policy
        from app.services.domain.media import media_service

        media = await media_service.simple_info(media_id)
        if not media:
            return None
        layout = await self.query.get_media_layout(media_id)
        decision = library_media_root_policy.build_from_library_layout(media, layout)
        return decision.media_root_dir if decision else None

    async def _resolve_media_root_dir_for_files(self, media_id: MediaID, files: list[LibraryFile]) -> str | None:
        from app.services.domain.library.media_root_policy import library_media_root_policy
        from app.services.domain.media import media_service

        media = await media_service.simple_info(media_id)
        if not media:
            return None
        layout = await self.query.get_media_layout_for_files(media_id, files)
        decision = library_media_root_policy.build_from_library_layout(media, layout)
        return decision.media_root_dir if decision else None

    @staticmethod
    def _group_delete_event_files(files: list[LibraryFile]) -> dict[str, list[LibraryFile]]:
        grouped: dict[str, list[LibraryFile]] = {}
        for file in files:
            grouped.setdefault(file.directory_id, []).append(file)
        return grouped

    async def _emit_media_delete_event(
        self,
        media_id: MediaID,
        paths: list[str],
        *,
        directory_id: str,
        delete_scope: str,
        media_root_dir: str | None = None,
        season_number: int | None = None,
    ) -> None:
        if not paths:
            return
        from app.services.domain.media import media_service

        media = await media_service.simple_info(media_id)
        if not media:
            return
        if media_id.media_type == MediaType.tv:
            media = media_service.apply_season_context(media, self._positive_season_number(season_number))
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.MEDIA_DELETED,
                media=media,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[EventEntityRef(type="media", id=str(media_id))],
            ),
            meta=MediaDeletedEventMeta(
                media_id=media_id,
                directory_id=directory_id,
                paths=paths,
                media_root_dir=media_root_dir,
                delete_scope=delete_scope,
            ),
        )
