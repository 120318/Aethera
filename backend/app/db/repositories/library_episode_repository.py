from __future__ import annotations

from typing import List

from sqlalchemy import delete, select

from app.db.sql.models import LibraryEpisodeORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.library import LibraryEpisode


class LibraryEpisodeRepository:
    @staticmethod
    def _to_model(row: LibraryEpisodeORM) -> LibraryEpisode:
        return LibraryEpisode.model_validate(
            {
                "media_id": row.media_id,
                "season": row.season,
                "episode": row.episode,
                "file_id": row.file_id,
                "created_at": row.created_at,
            }
        )

    async def get_all(self) -> List[LibraryEpisode]:
        with SessionLocal() as session:
            rows = session.execute(select(LibraryEpisodeORM)).scalars().all()
            return [self._to_model(row) for row in rows]

    async def insert(self, episode: LibraryEpisode) -> int:
        with SessionLocal() as session:
            row = LibraryEpisodeORM(
                media_id=str(episode.media_id),
                season=episode.season,
                episode=episode.episode,
                file_id=episode.file_id,
                created_at=episode.created_at,
            )
            session.add(row)
            session.commit()
            return int(row.id)

    async def find_by_media_id(self, media_id: MediaID) -> List[LibraryEpisode]:
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryEpisodeORM).where(LibraryEpisodeORM.media_id == str(media_id))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_and_season(self, media_id: MediaID, season: int) -> List[LibraryEpisode]:
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryEpisodeORM).where(
                    LibraryEpisodeORM.media_id == str(media_id),
                    LibraryEpisodeORM.season == season,
                )
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_file_ids(self, file_ids: List[str]) -> List[LibraryEpisode]:
        if not file_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryEpisodeORM).where(LibraryEpisodeORM.file_id.in_(file_ids))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def remove_by_file_ids(self, file_ids: List[str]) -> int:
        if not file_ids:
            return 0
        with SessionLocal() as session:
            result = session.execute(delete(LibraryEpisodeORM).where(LibraryEpisodeORM.file_id.in_(file_ids)))
            session.commit()
            return int(result.rowcount or 0)
