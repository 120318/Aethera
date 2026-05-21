from __future__ import annotations

import time

from sqlalchemy import desc, func, select, update

from app.db.sql.models import MediaSubscriptionSettingsORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import default_subscription_mode_for_media
from app.schemas.media_id import MediaID


def _storage_season(media_id: MediaID, season_number: int | None) -> int:
    if media_id.media_type.value != "tv":
        return 0
    return int(season_number or 0)


def _model_season(value: int | None) -> int | None:
    normalized = int(value or 0)
    return normalized if normalized > 0 else None


class MediaSubscriptionSettingsRepository:
    @staticmethod
    def _to_model(row: MediaSubscriptionSettingsORM) -> MediaSubscriptionSettings:
        media_id = MediaID.parse(row.media_id)
        return MediaSubscriptionSettings(
            sub_id=row.sub_id,
            media_id=media_id,
            media=row.media_json,
            season_number=_model_season(row.season_number),
            followed=bool(row.followed),
            subscription_mode=row.subscription_mode or default_subscription_mode_for_media(media_id),
            upgrade_policy=row.upgrade_policy_json,
            target_filters=row.target_filters_json,
            target_filter_config_id=row.target_filter_config_id,
            directory_id=row.directory_id,
            filter_config_id=row.filter_config_id,
            quality_profile_id=row.quality_profile_id,
            filters=row.filters_json,
            sites=row.sites_json,
            unmatched_rules=row.unmatched_rules_json or [],
            follow_reminded_air_date=row.follow_reminded_air_date,
            follow_reminded_digital_release_date=row.follow_reminded_digital_release_date,
            follow_reminded_physical_release_date=row.follow_reminded_physical_release_date,
            follow_reminded_at=row.follow_reminded_at,
            follow_reminded_digital_release_at=row.follow_reminded_digital_release_at,
            follow_reminded_physical_release_at=row.follow_reminded_physical_release_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_all(self) -> list[MediaSubscriptionSettings]:
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaSubscriptionSettingsORM).order_by(MediaSubscriptionSettingsORM.created_at.desc())
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionSettings | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionSettingsORM)
                .where(
                    MediaSubscriptionSettingsORM.media_id == str(media_id),
                    MediaSubscriptionSettingsORM.season_number == _storage_season(media_id, season_number),
                )
                .order_by(desc(MediaSubscriptionSettingsORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_by_sub_id(self, sub_id: str) -> MediaSubscriptionSettings | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionSettingsORM)
                .where(MediaSubscriptionSettingsORM.sub_id == sub_id)
                .order_by(desc(MediaSubscriptionSettingsORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def count_by_directory_id(self, directory_id: str) -> int:
        with SessionLocal() as session:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(MediaSubscriptionSettingsORM)
                    .where(MediaSubscriptionSettingsORM.directory_id == directory_id)
                ).scalar_one()
                or 0
            )

    async def update_directory_id(self, source_directory_id: str, target_directory_id: str) -> int:
        with SessionLocal() as session:
            result = session.execute(
                update(MediaSubscriptionSettingsORM)
                .where(MediaSubscriptionSettingsORM.directory_id == source_directory_id)
                .values(directory_id=target_directory_id, updated_at=time.time())
            )
            session.commit()
            return int(result.rowcount or 0)

    async def upsert(self, settings: MediaSubscriptionSettings) -> str:
        payload = settings.model_dump(mode="json")
        payload["media_id"] = str(settings.media_id)
        payload["season_number"] = _storage_season(settings.media_id, settings.season_number)
        payload["subscription_mode"] = settings.subscription_mode.value
        payload["media_json"] = payload.pop("media", None)
        payload["upgrade_policy_json"] = payload.pop("upgrade_policy", None)
        payload["target_filters_json"] = payload.pop("target_filters", None)
        payload["filters_json"] = payload.pop("filters", None)
        payload["sites_json"] = payload.pop("sites", None)
        payload["unmatched_rules_json"] = payload.pop("unmatched_rules", None) or None
        payload["sub_id"] = payload.pop("sub_id")
        with SessionLocal() as session:
            existing = session.execute(
                select(MediaSubscriptionSettingsORM).where(
                    MediaSubscriptionSettingsORM.media_id == str(settings.media_id),
                    MediaSubscriptionSettingsORM.season_number == payload["season_number"],
                )
            ).scalars().first()
            if existing:
                session.execute(
                    update(MediaSubscriptionSettingsORM)
                    .where(
                        MediaSubscriptionSettingsORM.media_id == str(settings.media_id),
                        MediaSubscriptionSettingsORM.season_number == payload["season_number"],
                    )
                    .values(**payload)
                )
            else:
                session.add(MediaSubscriptionSettingsORM(**payload))
            session.commit()
            return settings.sub_id

    async def update_media_snapshot(
        self,
        media_id: MediaID,
        season_number: int | None,
        media: MediaExecutionSnapshot,
    ) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(MediaSubscriptionSettingsORM)
                .where(
                    MediaSubscriptionSettingsORM.media_id == str(media_id),
                    MediaSubscriptionSettingsORM.season_number == _storage_season(media_id, season_number),
                )
                .values(
                    media_json=media.model_dump(mode="json"),
                    updated_at=time.time(),
                )
            )
            session.commit()
            return bool(result.rowcount)
