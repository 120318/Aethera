from __future__ import annotations

from datetime import datetime
import logging

from app.schemas.domain.download import EpisodeSelectionView, TaskData, TaskStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.exceptions import DownloadException, InvalidRequestException, ResourceNotFoundException
from app.services.domain.download.episode_selection import (
    available_episodes,
    episodes_for_file_indices,
    resolve_episode_selection,
)
from app.services.domain.download.lifecycle import DownloadCreationService
from app.services.platform.domain_lock_service import domain_lock_service


EDITABLE_STATUSES = {TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED}
logger = logging.getLogger("app.services.download.episode_selection")


class TaskEpisodeSelectionService:
    def __init__(self, repo, client_factory) -> None:
        self._repo = repo
        self._client_factory = client_factory

    def _view(self, task: TaskData) -> EpisodeSelectionView:
        metadata = task.metadata
        if not metadata or task.media_id.media_type != MediaType.tv:
            return EpisodeSelectionView()
        season_number = task.context.media.season_number
        available = available_episodes(metadata, season_number)
        if not available:
            return EpisodeSelectionView(episode_count=task.context.media.episodes_count)
        all_indices = [file_item.index for file_item in metadata.files]
        selected_indices = task.context.selected_files or all_indices
        return EpisodeSelectionView(
            selectable=task.status in EDITABLE_STATUSES,
            available_episodes=available,
            selected_episodes=episodes_for_file_indices(metadata, selected_indices),
            locked_episodes=episodes_for_file_indices(metadata, task.context.imported_file_indices),
            episode_count=task.context.media.episodes_count,
        )

    async def get_selection(self, task_id: str) -> EpisodeSelectionView:
        task = await self._repo.find_by_id(task_id)
        if not task:
            raise ResourceNotFoundException("backendErrors.taskNotFound")
        return self._view(task)

    async def update(self, task_id: str, episodes: list[int]) -> EpisodeSelectionView:
        snapshot = await self._repo.find_by_id(task_id)
        if not snapshot:
            raise ResourceNotFoundException("backendErrors.taskNotFound")
        if not snapshot.downloader_id:
            raise InvalidRequestException("backendErrors.episodeSelectionNotEditable")
        async with domain_lock_service.acquire_download_create(snapshot.downloader_id, snapshot.torrent_hash) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            return await self._update_locked(
                task_id, episodes, downloader_id=snapshot.downloader_id, torrent_hash=snapshot.torrent_hash,
            )

    async def _update_locked(
        self, task_id: str, episodes: list[int], *, downloader_id: str, torrent_hash: str,
    ) -> EpisodeSelectionView:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            task = await self._repo.find_by_id(task_id)
            if not task:
                raise ResourceNotFoundException("backendErrors.taskNotFound")
            # Re-read inside both locks; the pre-lock snapshot only determines the lock key.
            if task.downloader_id != downloader_id or task.torrent_hash != torrent_hash:
                raise DownloadException("backendErrors.taskBusy")
            if task.status not in EDITABLE_STATUSES or not task.metadata or not task.downloader_id:
                raise InvalidRequestException("backendErrors.episodeSelectionNotEditable")

            selected_indices, _effective_episodes = resolve_episode_selection(
                task.metadata,
                task.context.media.season_number,
                episodes,
            )
            if not selected_indices:
                raise InvalidRequestException("backendErrors.episodeSelectionInvalid")

            selected_indices = sorted(set(selected_indices) | set(task.context.imported_file_indices))
            if selected_indices == sorted(task.context.selected_files):
                return self._view(task)

            client = self._client_factory.get_download_client(task.downloader_id)
            if not client.capabilities().can_set_file_priority:
                raise InvalidRequestException("backendErrors.episodeSelectionUnsupported")
            live_files = await client.get_torrent_files(task.torrent_hash)
            if not live_files:
                raise DownloadException("backendErrors.taskNotFound")

            sibling_tasks = [
                sibling
                for sibling in await self._repo.find_by_hash_and_downloader(task.torrent_hash, task.downloader_id)
                if sibling.id != task.id and sibling.status != TaskStatus.VOID
            ]
            effective_indices = set(selected_indices)
            for sibling in sibling_tasks:
                sibling_files = sibling.metadata.files if sibling.metadata else task.metadata.files
                effective_indices.update(
                    sibling.context.selected_files
                    or [file_item.index for file_item in sibling_files]
                )

            all_indices = {file_item.index for file_item in task.metadata.files}
            effective_indices &= all_indices
            old_priorities = {file.index: file.priority for file in live_files if file.index in all_indices}
            new_priorities = {
                index: (max(1, old_priorities.get(index, 0)) if index in effective_indices else 0)
                for index in all_indices
            }
            changed = {
                index: priority
                for index, priority in new_priorities.items()
                if old_priorities.get(index) != priority
            }
            try:
                await self._apply_priorities(client, task.torrent_hash, changed)
                task.context.selected_files = selected_indices
                progress = DownloadCreationService._selected_file_progress(
                    selected_indices,
                    task.metadata.files,
                    live_files,
                )
                if progress is not None:
                    task.progress = progress
                task.updated_at = datetime.now()
                if not await self._repo.update_task(task):
                    raise RuntimeError("task update returned false")
            except Exception:
                await self._restore_priorities(client, task.torrent_hash, old_priorities, changed)
                raise
            return self._view(task)

    @staticmethod
    async def _apply_priorities(client, torrent_hash: str, priorities: dict[int, int]) -> None:
        for priority in sorted(set(priorities.values())):
            indices = sorted(index for index, value in priorities.items() if value == priority)
            if indices and not await client.set_file_priority(torrent_hash, indices, priority):
                raise DownloadException("backendErrors.episodeSelectionUpdateFailed")

    @staticmethod
    async def _restore_priorities(client, torrent_hash: str, old: dict[int, int], changed: dict[int, int]) -> None:
        for priority in sorted({old[index] for index in changed if index in old}):
            indices = sorted(index for index in changed if index in old and old[index] == priority)
            if indices:
                try:
                    await client.set_file_priority(torrent_hash, indices, priority)
                except Exception as exc:
                    logger.error(
                        "Failed to restore torrent file priorities: hash=%s indices=%s priority=%s error=%s",
                        torrent_hash,
                        indices,
                        priority,
                        exc,
                    )
