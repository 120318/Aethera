import logging
import time
import uuid
from pathlib import Path

from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.library_meta_repository import LibraryMetaRepository
from app.db.repositories.library_replace_repository import LibraryReplaceRepository
from app.schemas.domain.download import TransferFileResult
from app.schemas.domain.library import LibraryEpisode, LibraryFile, LibraryMeta
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.utils.library_paths import split_library_storage_path

logger = logging.getLogger("app.services.library")


class LibraryRegistrationWorker:
    def __init__(
        self,
        *,
        file_repo: LibraryFileRepository,
        episode_repo: LibraryEpisodeRepository,
        meta_repo: LibraryMetaRepository,
        replace_repo: LibraryReplaceRepository,
    ) -> None:
        self.file_repo = file_repo
        self.episode_repo = episode_repo
        self.meta_repo = meta_repo
        self.replace_repo = replace_repo

    async def upsert_media_entry(self, media_id: MediaID) -> None:
        mid_str = str(media_id)
        existing = await self.meta_repo.find_by_media_id(media_id)
        if not existing:
            await self.meta_repo.insert(
                LibraryMeta(
                    media_id=mid_str,
                    created_at=time.time(),
                    updated_at=time.time(),
                    status="planned",
                )
            )
            logger.debug("Created library meta entry for %s", mid_str)
            return
        existing.updated_at = time.time()
        await self.meta_repo.upsert_meta(existing)
        logger.debug("Updated library meta entry for %s", mid_str)

    async def register_transfer_results(
        self,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_results: list[TransferFileResult],
        season: int | None = None,
    ) -> None:
        await self.upsert_media_entry(media_id)
        for result in transfer_results:
            if season is not None:
                if not result.file_item.attrs:
                    result.file_item.attrs = ResourceAttributes()
                result.file_item.attrs.seasons = [season]

            existing_file = await self.file_repo.find_by_path(result.destination_path)
            if existing_file:
                logger.debug(
                    "Library file already exists, updating task binding: path=%s from_task=%s to_task=%s",
                    result.destination_path,
                    existing_file.task_id,
                    task_id,
                )
                await self.file_repo.update_task_binding(existing_file.id, task_id=task_id, directory_id=directory_id)
                continue

            file_id = str(uuid.uuid4())
            await self._add_library_file(file_id, task_id, directory_id, media_id, result)
            if result.episode_number and season is not None:
                await self._add_library_episode(media_id, season, result.episode_number, file_id)

        logger.info("Batch registered %d files for task %s", len(transfer_results), task_id)

    async def replace_task_entries(
        self,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_results: list[TransferFileResult],
        season: int | None = None,
        replacement_files: list[LibraryFile] | None = None,
    ) -> list[LibraryFile]:
        return await self.replace_repo.replace_task_entries(task_id, directory_id, media_id, transfer_results, season, replacement_files)

    async def _add_library_file(
        self,
        file_id: str,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_result: TransferFileResult,
    ) -> LibraryFile:
        file_item = transfer_result.file_item
        destination_path = Path(transfer_result.destination_path)
        final_path, final_file_name = split_library_storage_path(str(destination_path))
        file_record = LibraryFile(
            id=file_id,
            task_id=task_id,
            directory_id=directory_id,
            media_id=media_id,
            path=final_path,
            file_name=final_file_name,
            file_size=file_item.size,
            file_index=transfer_result.file_index,
            created_at=time.time(),
            resource_attributes=file_item.attrs or ResourceAttributes(),
        )
        await self.file_repo.insert(file_record)
        logger.debug("Added library file: %s (Root: %s)", final_file_name, final_path)
        return file_record

    async def _add_library_episode(
        self,
        media_id: MediaID,
        season: int,
        episode: int,
        file_id: str,
    ) -> LibraryEpisode:
        episode_record = LibraryEpisode(
            media_id=media_id,
            season=season,
            episode=episode,
            file_id=file_id,
            created_at=time.time(),
        )
        await self.episode_repo.insert(episode_record)
        logger.debug("Added library episode: %s S%02dE%02d", media_id, season, episode)
        return episode_record
