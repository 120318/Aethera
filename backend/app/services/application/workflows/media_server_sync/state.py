from app.db.repositories.metadata_sync_repository import MetadataSyncRepository
from app.schemas.config import MediaServerSyncConfig
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerSyncDetectNeeds, MediaServerSyncState
from app.schemas.media_id import MediaID


class MediaServerSyncStateService:
    def __init__(self) -> None:
        self._repo = MetadataSyncRepository()

    def fetch_state(self, media_server_id: str, media_id: MediaID) -> MediaServerSyncState | None:
        return self._repo.fetch_state(media_server_id, media_id)

    def list_due_ids(self, media_server_id: str, now: float, limit: int) -> list[MediaID]:
        return self._repo.list_due_ids(media_server_id, now, limit)

    def list_all_media_ids(self, media_server_id: str) -> set[MediaID]:
        return self._repo.list_all_media_ids(media_server_id)

    def get_or_create_state(self, media_server_id: str, media_id: MediaID) -> MediaServerSyncState:
        return self.fetch_state(media_server_id, media_id) or MediaServerSyncState(
            media_server_id=media_server_id,
            media_id=media_id,
        )

    def touch_state(self, media: MediaFullInfo, media_server_id: str, now: float) -> None:
        existing = self._repo.fetch_state(media_server_id, media.media_id)
        if existing:
            existing.next_due_at = min(existing.next_due_at or now, now + 60)
            self._repo.save_state(existing)
            return
        self._repo.save_state(
            MediaServerSyncState(
                media_server_id=media_server_id,
                media_id=media.media_id,
                media_type=media.media_type,
                next_due_at=now + 60,
                last_error="",
            )
        )

    def bootstrap_due_queue(
        self,
        media_server_id: str,
        candidates: list[MediaID],
        now: float,
        max_new: int,
        interval_hours: int,
    ) -> None:
        existing_ids = self.list_all_media_ids(media_server_id)
        interval = max(1, interval_hours) * 3600
        created = 0
        for media_id in candidates:
            if created >= max_new or media_id in existing_ids:
                continue
            self._repo.save_state(
                MediaServerSyncState(
                    media_server_id=media_server_id,
                    media_id=media_id,
                    media_type=media_id.media_type,
                    next_due_at=now + (created % 60) * (interval / 60),
                    last_error="",
                )
            )
            created += 1

    def record_checked(
        self,
        state: MediaServerSyncState,
        needs: MediaServerSyncDetectNeeds,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> None:
        state.last_check_at = now
        state.missing_flags = needs.missing_flags
        state.updated_paths = needs.updated_paths
        state.last_error = ",".join(needs.missing_flags) if needs.missing_flags else ""
        state.next_due_at = now + sync_cfg.interval_hours * 3600
        self._repo.save_state(state)

    def record_success(
        self,
        state: MediaServerSyncState,
        needs: MediaServerSyncDetectNeeds,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> None:
        state.last_check_at = now
        state.last_success_at = now
        state.next_due_at = now + sync_cfg.interval_hours * 3600
        state.failure_count = 0
        state.last_error = ""
        state.missing_flags = needs.missing_flags
        state.updated_paths = needs.updated_paths
        self._repo.save_state(state)

    def record_failure(
        self,
        state: MediaServerSyncState,
        error: ValueError,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> None:
        next_failure_count = state.failure_count + 1
        state.last_check_at = now
        state.failure_count = next_failure_count
        state.last_error = str(error)
        state.next_due_at = now + min(
            sync_cfg.max_backoff_hours * 3600,
            (2 ** min(next_failure_count, 10)) * 60,
        )
        self._repo.save_state(state)


media_server_sync_state = MediaServerSyncStateService()
