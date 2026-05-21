import time
from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.library_meta_repository import LibraryMetaRepository
from app.db.repositories.managed_media_profile_repository import ManagedMediaProfileRepository
from app.db.repositories.task_repository import TaskRepository
from app.schemas.media_id import MediaID
from app.services.domain.subscription.query_service import subscription_query_service


class MediaProfileLifecycle:
    def __init__(
        self,
        *,
        profile_repo: ManagedMediaProfileRepository,
        task_repo: TaskRepository,
        episode_repo: LibraryEpisodeRepository,
        file_repo: LibraryFileRepository,
        meta_repo: LibraryMetaRepository,
    ) -> None:
        self.profile_repo = profile_repo
        self.task_repo = task_repo
        self.episode_repo = episode_repo
        self.file_repo = file_repo
        self.meta_repo = meta_repo

    async def build_active_media_map(self) -> dict[MediaID, None]:
        from app.services.domain.download import download_service

        subscriptions = await subscription_query_service.list_states()
        tasks = await download_service.get_tasks()
        episodes = await self.episode_repo.get_all()
        metas = await self.meta_repo.get_all()
        files = await self.file_repo.get_all()

        media_map: dict[MediaID, None] = {}
        active_subscriptions = [sub for sub in subscriptions if sub.active or sub.followed]
        active_subscriptions.sort(key=lambda sub: sub.created_at, reverse=True)
        for subscription in active_subscriptions:
            if subscription.media_id:
                media_map[subscription.media_id] = None

        for task in tasks:
            if task.media_id:
                media_map[task.media_id] = None
        for episode in episodes:
            if episode.media_id:
                media_map[episode.media_id] = None
        for meta in metas:
            if meta.media_id and meta.status != "archived":
                media_map[meta.media_id] = None

        task_media_by_id = {task.id: task.media_id for task in tasks if task.id and task.media_id}
        for file_row in files:
            if file_row.task_id in task_media_by_id:
                media_map[task_media_by_id[file_row.task_id]] = None
        return media_map

    async def is_managed_media(self, media_id: MediaID) -> bool:
        profile = await self.profile_repo.find_by_media_id(media_id)
        return bool(profile and profile.is_active)

    async def _has_media_references(self, media_id: MediaID) -> bool:
        if await self.task_repo.find_by_media_id(media_id):
            return True
        if await self.episode_repo.find_by_media_id(media_id):
            return True
        meta = await self.meta_repo.find_by_media_id(media_id)
        return bool(meta and meta.status != "archived")

    async def mark_profile_inactive_if_unmanaged(self, media_id: MediaID) -> bool:
        profile = await self.profile_repo.find_by_media_id(media_id)
        if not profile or not profile.is_active:
            return False
        if await self._has_media_references(media_id):
            return False
        now = time.time()
        profile.is_active = False
        profile.inactive_since = now
        profile.updated_at = now
        await self.profile_repo.upsert_profile(profile)
        return True

    async def mark_inactive_profiles(self, active_media_ids: list[MediaID]) -> int:
        now = time.time()
        active_set = {str(media_id) for media_id in active_media_ids}
        profiles = await self.profile_repo.get_all()
        marked = 0
        for profile in profiles:
            if str(profile.media_id) in active_set:
                if not profile.is_active or profile.inactive_since is not None:
                    profile.is_active = True
                    profile.inactive_since = None
                    profile.last_seen_at = now
                    profile.updated_at = now
                    await self.profile_repo.upsert_profile(profile)
                continue
            if profile.is_active:
                profile.is_active = False
                profile.inactive_since = now
                profile.updated_at = now
                await self.profile_repo.upsert_profile(profile)
                marked += 1
        return marked

    async def cleanup_inactive_profiles(self) -> int:
        active_map = await self.build_active_media_map()
        active_set = {str(media_id) for media_id in active_map.keys()}
        profiles = await self.profile_repo.find_inactive()
        now = time.time()
        removed = 0
        for profile in profiles:
            if str(profile.media_id) in active_set or await self.is_managed_media(profile.media_id):
                profile.is_active = True
                profile.inactive_since = None
                profile.last_seen_at = now
                profile.updated_at = now
                await self.profile_repo.upsert_profile(profile)
                continue
            removed += await self.profile_repo.remove_by_media_id(profile.media_id)
        return removed
