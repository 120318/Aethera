from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select

from app.schemas.media_id import MediaID
from app.db.sql.models import ManagedMediaProfileORM, MediaProfileScopeORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.managed_media_profile import ManagedMediaProfile


class ManagedMediaProfileRepository:
    @staticmethod
    def _to_model(row: ManagedMediaProfileORM) -> ManagedMediaProfile:
        return ManagedMediaProfile.model_validate(
            {
                "media_id": row.media_id,
                "media_type": row.media_type,
                "title": row.title,
                "original_title": row.original_title,
                "poster_path": row.poster_path,
                "backdrop_path": row.backdrop_path,
                "logo_path": row.logo_path,
                "year": row.year,
                "overview": row.overview,
                "genres": row.genres_json,
                "imdb_id": row.imdb_id,
                "douban_id": row.douban_id,
                "tmdb_id": row.tmdb_id,
                "primary_metadata_source": row.primary_metadata_source or "douban",
                "metadata_capabilities": row.metadata_capabilities_json or {},
                "tvdb_id": row.tvdb_id,
                "actors": row.actors_json,
                "directors": row.directors_json,
                "studios": row.studios_json,
                "vendors": [],
                "duration": row.duration,
                "rating_count": row.rating_count,
                "vote_average": row.vote_average,
                "vote_count": row.vote_count,
                "rating_source": row.rating_source,
                "douban_vote_average": row.douban_vote_average,
                "douban_rating_count": row.douban_rating_count,
                "tmdb_vote_average": row.tmdb_vote_average,
                "tmdb_rating_count": row.tmdb_rating_count,
                "release_date": row.release_date,
                "seasons_count": row.seasons_count,
                "episodes_count": row.episodes_count,
                "seasons": [],
                "status": row.status,
                "original_language": row.original_language,
                "status_label": None,
                "first_air_date": None,
                "aired_episode_count": 0,
                "latest_aired_episode": None,
                "next_episode_to_air": None,
                "premiere_release_date": None,
                "theatrical_limited_release_date": None,
                "theatrical_release_date": None,
                "digital_release_date": None,
                "physical_release_date": None,
                "tv_release_date": None,
                "release_dates": [],
                "networks": [],
                "online_platforms": [],
                "airings": [],
                "is_active": bool(row.is_active),
                "last_seen_at": row.last_seen_at,
                "inactive_since": row.inactive_since,
                "detail_ready": bool(row.detail_ready),
                "simple_info_updated_at": row.simple_info_updated_at,
                "detail_updated_at": row.detail_updated_at,
                "schedule_updated_at": row.schedule_updated_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    async def get_all(self) -> List[ManagedMediaProfile]:
        with SessionLocal() as session:
            rows = session.execute(select(ManagedMediaProfileORM)).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_id(self, media_id: MediaID) -> Optional[ManagedMediaProfile]:
        with SessionLocal() as session:
            row = session.get(ManagedMediaProfileORM, str(media_id))
            return self._to_model(row) if row else None

    async def find_by_media_ids(self, media_ids: List[MediaID]) -> List[ManagedMediaProfile]:
        if not media_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(ManagedMediaProfileORM).where(ManagedMediaProfileORM.media_id.in_([str(media_id) for media_id in media_ids]))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_active(self) -> List[ManagedMediaProfile]:
        with SessionLocal() as session:
            rows = session.execute(
                select(ManagedMediaProfileORM).where(ManagedMediaProfileORM.is_active == 1)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_inactive(self) -> List[ManagedMediaProfile]:
        with SessionLocal() as session:
            rows = session.execute(
                select(ManagedMediaProfileORM).where(ManagedMediaProfileORM.is_active == 0)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def upsert_profile(self, profile: ManagedMediaProfile) -> bool:
        with SessionLocal() as session:
            row = session.get(ManagedMediaProfileORM, str(profile.media_id))
            values = {
                "media_type": profile.media_type,
                "title": profile.title,
                "original_title": profile.original_title,
                "poster_path": profile.poster_path,
                "backdrop_path": profile.backdrop_path,
                "logo_path": profile.logo_path,
                "year": profile.year,
                "overview": profile.overview,
                "genres_json": profile.genres,
                "imdb_id": profile.imdb_id,
                "douban_id": profile.douban_id,
                "tmdb_id": profile.tmdb_id,
                "primary_metadata_source": profile.primary_metadata_source,
                "metadata_capabilities_json": profile.metadata_capabilities.model_dump(mode="json"),
                "tvdb_id": profile.tvdb_id,
                "actors_json": [item.model_dump(mode="json") for item in profile.actors],
                "directors_json": [item.model_dump(mode="json") for item in profile.directors],
                "studios_json": profile.studios,
                "duration": profile.duration,
                "rating_count": profile.rating_count,
                "vote_average": profile.vote_average,
                "vote_count": profile.vote_count,
                "rating_source": profile.rating_source,
                "douban_vote_average": profile.douban_vote_average,
                "douban_rating_count": profile.douban_rating_count,
                "tmdb_vote_average": profile.tmdb_vote_average,
                "tmdb_rating_count": profile.tmdb_rating_count,
                "release_date": profile.release_date,
                "seasons_count": profile.seasons_count,
                "episodes_count": profile.episodes_count,
                "status": profile.status,
                "original_language": profile.original_language,
                "is_active": bool(profile.is_active),
                "last_seen_at": profile.last_seen_at,
                "inactive_since": profile.inactive_since,
                "detail_ready": bool(profile.detail_ready),
                "simple_info_updated_at": profile.simple_info_updated_at,
                "detail_updated_at": profile.detail_updated_at,
                "schedule_updated_at": profile.schedule_updated_at,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
            if row is None:
                row = ManagedMediaProfileORM(media_id=str(profile.media_id), **values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            return True

    async def remove_inactive_before(self, cutoff: float) -> int:
        with SessionLocal() as session:
            result = session.execute(
                delete(ManagedMediaProfileORM).where(
                    ManagedMediaProfileORM.is_active == 0,
                    ManagedMediaProfileORM.inactive_since.is_not(None),
                    ManagedMediaProfileORM.inactive_since <= cutoff,
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    async def remove_by_media_id(self, media_id: MediaID) -> int:
        with SessionLocal() as session:
            session.execute(
                delete(MediaProfileScopeORM).where(MediaProfileScopeORM.media_id == str(media_id))
            )
            result = session.execute(
                delete(ManagedMediaProfileORM).where(ManagedMediaProfileORM.media_id == str(media_id))
            )
            session.commit()
            return int(result.rowcount or 0)
