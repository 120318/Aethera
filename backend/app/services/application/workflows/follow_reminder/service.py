from __future__ import annotations

import logging
import time
from datetime import date

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.event_meta import FollowReleasedEventMeta
from app.schemas.domain.media import MediaIdentity
from app.schemas.domain.media_subscription_state import MediaSubscriptionStatePatch
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.base import AppException
from app.services.audit.event_service import event_service
from app.services.domain.media import media_service
from app.services.domain.subscription.command_service import subscription_command_service
from app.services.domain.subscription.query_service import subscription_query_service

logger = logging.getLogger("app.services.follow_reminder")


def _parse_ymd(d: str | None) -> date | None:
    if not d:
        return None
    try:
        s = str(d).strip()
        if len(s) >= 10:
            s = s[:10]
        y, m, dd = s.split("-")
        return date(int(y), int(m), int(dd))
    except ValueError:
        return None


def _should_emit_reminder(today: date, air_date: date, window_days: int, reminded_air_date: str | None) -> bool:
    _ = window_days
    if air_date > today:
        return False
    if reminded_air_date:
        prev = _parse_ymd(reminded_air_date)
        if prev and prev == air_date:
            return False
    return True


class FollowReminderService:
    def _emit_follow_released_event(
        self,
        *,
        sub_id: str,
        media: MediaIdentity,
        media_id,
        air_date: str,
        release_kind: str = "theatrical",
    ) -> None:
        event_type = EventTypes.FOLLOW_RELEASED
        if release_kind == "digital":
            event_type = EventTypes.FOLLOW_DIGITAL_RELEASED
        elif release_kind == "physical":
            event_type = EventTypes.FOLLOW_PHYSICAL_RELEASED
        event_service.emit_media(
            MediaEventCreate(
                type=event_type,
                level=EventLevel.info,
                media=media,
                subscription_id=sub_id,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[EventEntityRef(type="media", id=str(media_id))],
            ),
            meta=FollowReleasedEventMeta(air_date=air_date, release_kind=release_kind),
        )

    async def _handle_movie_follow_release(self, sub, media, today: date, window_days: int) -> None:
        sub_id = sub.sub_id
        if not sub_id:
            return
        release_date = media.theatrical_release_date or media.release_date
        release_dt = _parse_ymd(release_date)
        patch = MediaSubscriptionStatePatch()
        if release_date and release_dt and _should_emit_reminder(today, release_dt, window_days, sub.follow_reminded_air_date):
            self._emit_follow_released_event(sub_id=sub_id, media=media, media_id=sub.media_id, air_date=release_date)
            patch.follow_reminded_air_date = release_date
            patch.follow_reminded_at = time.time()
        digital_date = media.digital_release_date
        digital_dt = _parse_ymd(digital_date)
        if digital_date and digital_dt and _should_emit_reminder(today, digital_dt, window_days, sub.follow_reminded_digital_release_date):
            self._emit_follow_released_event(sub_id=sub_id, media=media, media_id=sub.media_id, air_date=digital_date, release_kind="digital")
            patch.follow_reminded_digital_release_date = digital_date
            patch.follow_reminded_digital_release_at = time.time()
        physical_date = media.physical_release_date
        physical_dt = _parse_ymd(physical_date)
        if physical_date and physical_dt and _should_emit_reminder(today, physical_dt, window_days, sub.follow_reminded_physical_release_date):
            self._emit_follow_released_event(sub_id=sub_id, media=media, media_id=sub.media_id, air_date=physical_date, release_kind="physical")
            patch.follow_reminded_physical_release_date = physical_date
            patch.follow_reminded_physical_release_at = time.time()
        if patch.model_fields_set:
            await subscription_command_service.patch_settings_by_sub_id(sub_id, patch)

    async def _handle_tv_follow_release(self, sub, media, today: date, window_days: int) -> None:
        air_date_str = media.first_air_date or media.release_date
        air_dt = _parse_ymd(air_date_str)
        if not air_dt or not _should_emit_reminder(today, air_dt, window_days, sub.follow_reminded_air_date):
            return
        if not sub.sub_id:
            return
        self._emit_follow_released_event(sub_id=sub.sub_id, media=media, media_id=sub.media_id, air_date=air_date_str)
        await subscription_command_service.patch_settings_by_sub_id(
            sub.sub_id,
            MediaSubscriptionStatePatch(follow_reminded_air_date=air_date_str, follow_reminded_at=time.time()),
        )

    async def run_once(self, window_days: int = 7) -> None:
        today = date.today()

        subs = await subscription_query_service.list_states()
        for sub in subs:
            try:
                if not sub.followed:
                    continue

                mid = sub.media_id
                if not mid:
                    continue

                media = await media_service.cached_info(mid)
                if not media:
                    continue

                if media.media_id.media_type == MediaType.movie:
                    await self._handle_movie_follow_release(sub, media, today, window_days)
                else:
                    await self._handle_tv_follow_release(sub, media, today, window_days)
            except (AppException, RuntimeError, ValueError) as exc:
                logger.warning("Follow reminder sweep failed for sub: %s", exc)


follow_reminder_service = FollowReminderService()
