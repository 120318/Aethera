import time

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.sqlite import insert

from app.db.sql.models import MediaExternalMappingORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.search_models import MediaSearchResult
from app.schemas.media_id import MediaID
from app.schemas.persistence.media_external_mapping import MediaExternalMappingRecord


class MediaExternalMappingRepository:
    def _to_record(self, row: MediaExternalMappingORM) -> MediaExternalMappingRecord:
        return MediaExternalMappingRecord.model_validate(row, from_attributes=True)

    def find_by_media_id(self, media_id: MediaID) -> MediaExternalMappingRecord | None:
        if media_id.media_type.value == "tv":
            return None
        return self.find_by_media_id_and_season(media_id, 0)

    def find_by_media_id_and_season(
        self,
        media_id: MediaID,
        season_number: int | None,
    ) -> MediaExternalMappingRecord | None:
        with SessionLocal() as session:
            statement = select(MediaExternalMappingORM).where(MediaExternalMappingORM.media_id == str(media_id))
            if media_id.media_type.value == "tv":
                if season_number is None or season_number <= 0:
                    return None
                statement = statement.where(MediaExternalMappingORM.season_number == int(season_number))
            else:
                statement = statement.where(MediaExternalMappingORM.season_number == 0)
            row = session.execute(statement).scalars().first()
            return self._to_record(row) if row else None

    def find_by_douban_id(self, douban_id: str, media_type: str) -> MediaExternalMappingRecord | None:
        normalized = str(douban_id or "").strip()
        if not normalized:
            return None
        with SessionLocal() as session:
            row = session.execute(
                select(MediaExternalMappingORM)
                .where(
                    MediaExternalMappingORM.douban_id == normalized,
                    MediaExternalMappingORM.media_type == media_type,
                )
                .order_by(MediaExternalMappingORM.updated_at.desc())
            ).scalars().first()
            return self._to_record(row) if row else None

    def find_by_douban_id_and_season(
        self,
        douban_id: str,
        media_type: str,
        season_number: int | None,
    ) -> MediaExternalMappingRecord | None:
        normalized = str(douban_id or "").strip()
        if not normalized:
            return None
        normalized_season = int(season_number) if media_type == "tv" and season_number else 0
        if media_type == "tv" and normalized_season <= 0:
            return None
        with SessionLocal() as session:
            row = session.execute(
                select(MediaExternalMappingORM)
                .where(
                    MediaExternalMappingORM.douban_id == normalized,
                    MediaExternalMappingORM.media_type == media_type,
                    MediaExternalMappingORM.season_number == normalized_season,
                )
                .order_by(MediaExternalMappingORM.updated_at.desc())
            ).scalars().first()
            return self._to_record(row) if row else None

    def exists_by_media_id(self, media_id: MediaID) -> bool:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaExternalMappingORM.media_id)
                .where(MediaExternalMappingORM.media_id == str(media_id))
                .limit(1)
            ).first()
            return row is not None

    def find_viewed_search_results(self, items: list[MediaSearchResult]) -> set[int]:
        media_keys: dict[tuple[str, str], set[int]] = {}
        douban_keys: dict[tuple[str, str], set[int]] = {}
        for index, item in enumerate(items):
            if item.media_id:
                media_keys.setdefault((str(item.media_id), item.media_id.media_type.value), set()).add(index)
            elif item.source == "tmdb" and item.source_id and item.media_type:
                media_keys.setdefault((f"tmdb:{item.media_type.value}:{item.source_id}", item.media_type.value), set()).add(index)
            if item.source == "douban" and item.source_id and item.media_type:
                douban_keys.setdefault((item.source_id, item.media_type.value), set()).add(index)
            elif item.douban_id and item.media_type:
                douban_keys.setdefault((item.douban_id, item.media_type.value), set()).add(index)

        predicates = [
            (
                (MediaExternalMappingORM.media_id == media_id)
                & (MediaExternalMappingORM.media_type == media_type)
            )
            for media_id, media_type in media_keys
        ] + [
            (
                (MediaExternalMappingORM.douban_id == douban_id)
                & (MediaExternalMappingORM.media_type == media_type)
            )
            for douban_id, media_type in douban_keys
        ]
        if not predicates:
            return set()

        with SessionLocal() as session:
            rows = session.execute(select(MediaExternalMappingORM).where(or_(*predicates))).scalars().all()
        viewed: set[int] = set()
        for row in rows:
            viewed.update(media_keys.get((row.media_id, row.media_type), set()))
            if row.douban_id:
                viewed.update(douban_keys.get((row.douban_id, row.media_type), set()))
        return viewed

    def upsert(
        self,
        media_id: MediaID,
        tmdb_id: int | None,
        imdb_id: str | None,
        douban_id: str | None,
        season_number: int | None,
        episode_count_override: int | None = None,
    ) -> None:
        normalized_season = int(season_number) if media_id.media_type.value == "tv" and season_number else 0
        if media_id.media_type.value == "tv" and (normalized_season is None or normalized_season <= 0):
            return
        updated_at = time.time()
        update_values = {
            "media_type": media_id.media_type.value,
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "douban_id": douban_id,
            "episode_count_override": episode_count_override,
            "updated_at": updated_at,
        }
        with SessionLocal() as session:
            if douban_id:
                source_rows = session.execute(
                    select(MediaExternalMappingORM)
                    .where(
                        MediaExternalMappingORM.douban_id == douban_id,
                        MediaExternalMappingORM.media_type == media_id.media_type.value,
                        MediaExternalMappingORM.season_number == normalized_season,
                        MediaExternalMappingORM.media_id != str(media_id),
                    )
                    .order_by(MediaExternalMappingORM.updated_at.desc())
                ).scalars().all()
                if source_rows:
                    target_exists = session.execute(
                        select(MediaExternalMappingORM.media_id)
                        .where(
                            MediaExternalMappingORM.media_id == str(media_id),
                            MediaExternalMappingORM.season_number == normalized_season,
                        )
                        .limit(1)
                    ).first()
                    if not target_exists:
                        source_row = source_rows[0]
                        session.execute(
                            update(MediaExternalMappingORM)
                            .where(
                                MediaExternalMappingORM.media_id == source_row.media_id,
                                MediaExternalMappingORM.season_number == source_row.season_number,
                            )
                            .values(
                                media_id=str(media_id),
                                season_number=normalized_season,
                                **update_values,
                            )
                        )
                        source_rows = source_rows[1:]
                    if source_rows:
                        stale_keys = [
                            (row.media_id, row.season_number)
                            for row in source_rows
                        ]
                        session.execute(
                            delete(MediaExternalMappingORM).where(
                                or_(*[
                                    (
                                        (MediaExternalMappingORM.media_id == stale_media_id)
                                        & (MediaExternalMappingORM.season_number == stale_season_number)
                                    )
                                    for stale_media_id, stale_season_number in stale_keys
                                ])
                            )
                        )
                    if not target_exists:
                        session.commit()
                        return
            statement = insert(MediaExternalMappingORM).values(
                media_id=str(media_id),
                media_type=media_id.media_type.value,
                season_number=normalized_season,
                tmdb_id=tmdb_id,
                imdb_id=imdb_id,
                douban_id=douban_id,
                episode_count_override=episode_count_override,
                updated_at=updated_at,
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[
                        MediaExternalMappingORM.media_id,
                        MediaExternalMappingORM.season_number,
                    ],
                    set_=update_values,
                )
            )
            session.commit()

    def remove(self, media_id: MediaID, season_number: int | None = None) -> bool:
        with SessionLocal() as session:
            statement = delete(MediaExternalMappingORM).where(MediaExternalMappingORM.media_id == str(media_id))
            if media_id.media_type.value == "tv":
                if season_number is None or season_number <= 0:
                    return False
                statement = statement.where(MediaExternalMappingORM.season_number == int(season_number))
            else:
                statement = statement.where(MediaExternalMappingORM.season_number == 0)
            result = session.execute(statement)
            session.commit()
            return bool(result.rowcount)
