from __future__ import annotations

from sqlalchemy import delete, select

from app.db.sql.models import MediaProfileScopeORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.media_profile_scope import MediaProfileScope
from app.schemas.media_id import MediaID


class MediaProfileScopeRepository:
    @staticmethod
    def _to_model(row: MediaProfileScopeORM) -> MediaProfileScope:
        return MediaProfileScope.model_validate(
            {
                "media_id": row.media_id,
                "season_number": row.season_number,
                "media_type": row.media_type,
                "name": row.name,
                "air_date": row.air_date,
                "episode_count": row.episode_count,
                "episode_count_override": row.episode_count_override,
                "poster_path": row.poster_path,
                "douban_id": row.douban_id,
                "douban_vote_average": row.douban_vote_average,
                "douban_rating_count": row.douban_rating_count,
                "first_air_date": row.first_air_date,
                "status_label": row.status_label,
                "aired_episode_count": row.aired_episode_count,
                "latest_aired_episode": row.latest_aired_episode_json,
                "next_episode_to_air": row.next_episode_to_air_json,
                "premiere_release_date": row.premiere_release_date,
                "theatrical_limited_release_date": row.theatrical_limited_release_date,
                "theatrical_release_date": row.theatrical_release_date,
                "digital_release_date": row.digital_release_date,
                "physical_release_date": row.physical_release_date,
                "tv_release_date": row.tv_release_date,
                "release_dates": row.release_dates_json or [],
                "platforms": row.platforms_json or [],
                "airings": row.airings_json or [],
                "updated_at": row.updated_at,
            }
        )

    async def find_by_media_id(self, media_id: MediaID) -> list[MediaProfileScope]:
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaProfileScopeORM)
                .where(MediaProfileScopeORM.media_id == str(media_id))
                .order_by(MediaProfileScopeORM.season_number.asc())
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, list[MediaProfileScope]]:
        if not media_ids:
            return {}
        media_values = [str(media_id) for media_id in media_ids]
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaProfileScopeORM)
                .where(MediaProfileScopeORM.media_id.in_(media_values))
                .order_by(MediaProfileScopeORM.media_id.asc(), MediaProfileScopeORM.season_number.asc())
            ).scalars().all()

        scopes_by_media_id: dict[str, list[MediaProfileScope]] = {}
        for row in rows:
            scopes_by_media_id.setdefault(row.media_id, []).append(self._to_model(row))
        return scopes_by_media_id

    async def find_by_media_id_and_season(self, media_id: MediaID, season_number: int) -> MediaProfileScope | None:
        with SessionLocal() as session:
            row = session.get(MediaProfileScopeORM, (str(media_id), int(season_number)))
            return self._to_model(row) if row else None

    async def upsert_scope(self, scope: MediaProfileScope) -> bool:
        with SessionLocal() as session:
            row = session.get(MediaProfileScopeORM, (str(scope.media_id), int(scope.season_number)))
            values = {
                "media_type": scope.media_type,
                "name": scope.name,
                "air_date": scope.air_date,
                "episode_count": scope.episode_count,
                "episode_count_override": scope.episode_count_override,
                "poster_path": scope.poster_path,
                "douban_id": scope.douban_id,
                "douban_vote_average": scope.douban_vote_average,
                "douban_rating_count": scope.douban_rating_count,
                "first_air_date": scope.first_air_date,
                "status_label": scope.status_label,
                "aired_episode_count": scope.aired_episode_count,
                "latest_aired_episode_json": scope.latest_aired_episode.model_dump(mode="json") if scope.latest_aired_episode else None,
                "next_episode_to_air_json": scope.next_episode_to_air.model_dump(mode="json") if scope.next_episode_to_air else None,
                "premiere_release_date": scope.premiere_release_date,
                "theatrical_limited_release_date": scope.theatrical_limited_release_date,
                "theatrical_release_date": scope.theatrical_release_date,
                "digital_release_date": scope.digital_release_date,
                "physical_release_date": scope.physical_release_date,
                "tv_release_date": scope.tv_release_date,
                "release_dates_json": [item.model_dump(mode="json") for item in scope.release_dates],
                "platforms_json": [item.model_dump(mode="json") for item in scope.platforms],
                "airings_json": [item.model_dump(mode="json") for item in scope.airings],
                "updated_at": scope.updated_at,
            }
            if row is None:
                row = MediaProfileScopeORM(media_id=str(scope.media_id), season_number=scope.season_number, **values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            return True

    async def upsert_scopes(self, scopes: list[MediaProfileScope]) -> bool:
        for scope in scopes:
            await self.upsert_scope(scope)
        return True

    async def remove_by_media_id(self, media_id: MediaID) -> int:
        with SessionLocal() as session:
            result = session.execute(
                delete(MediaProfileScopeORM).where(MediaProfileScopeORM.media_id == str(media_id))
            )
            session.commit()
            return int(result.rowcount or 0)
