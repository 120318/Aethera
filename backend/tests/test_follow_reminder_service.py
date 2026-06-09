from types import SimpleNamespace
from datetime import date, timedelta

import pytest

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.audit.event_message_i18n import event_message_key, event_message_params
from app.services.application.workflows.follow_reminder import follow_reminder_service

pytestmark = pytest.mark.drift


def _ymd(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


def _movie(**updates) -> MediaFullInfo:
    theatrical_date = _ymd(-1)
    digital_date = _ymd(-2)
    payload = {
        "media_id": MediaID.parse("tmdb:movie:1"),
        "media_type": MediaType.movie,
        "title": "Sample",
        "year": date.today().year,
        "release_date": theatrical_date,
        "theatrical_release_date": theatrical_date,
        "digital_release_date": digital_date,
    }
    payload.update(updates)
    return MediaFullInfo(**payload)


@pytest.mark.asyncio
async def test_follow_reminder_emits_movie_theatrical_digital_and_physical_events(monkeypatch):
    physical_date = _ymd(-3)
    media = _movie(physical_release_date=physical_date)
    sub = SimpleNamespace(
        media_id=media.media_id,
        sub_id="sub-1",
        followed=True,
        follow_reminded_air_date=None,
        follow_reminded_digital_release_date=None,
        follow_reminded_physical_release_date=None,
    )
    emitted = []
    patches = []

    async def fake_list():
        return [sub]

    async def fake_execution_snapshot(media_id, *, season_number=None):
        assert season_number is None
        return media

    async def fake_patch_by_sub_id(sub_id, patch):
        patches.append((sub_id, patch))

    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.media_service.resolve_execution_snapshot", fake_execution_snapshot)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.event_service.emit_media", lambda event, meta=None: emitted.append((event, meta)))
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_command_service.patch_settings_by_sub_id", fake_patch_by_sub_id)

    await follow_reminder_service.run_once()

    assert [event.type for event, _ in emitted] == [
        EventTypes.FOLLOW_RELEASED,
        EventTypes.FOLLOW_DIGITAL_RELEASED,
        EventTypes.FOLLOW_PHYSICAL_RELEASED,
    ]
    assert [event_message_key(event.type) for event, _ in emitted] == [
        "eventMessages.followReleased",
        "eventMessages.followDigitalReleased",
        "eventMessages.followPhysicalReleased",
    ]
    assert [event_message_params(event, meta)["air_date"] for event, meta in emitted] == [
        media.theatrical_release_date,
        media.digital_release_date,
        physical_date,
    ]
    assert patches[0][1].follow_reminded_air_date == media.theatrical_release_date
    assert patches[0][1].follow_reminded_digital_release_date == media.digital_release_date
    assert patches[0][1].follow_reminded_physical_release_date == physical_date


@pytest.mark.asyncio
async def test_follow_reminder_emits_only_available_movie_release(monkeypatch):
    media = _movie(release_date=None, theatrical_release_date=None, digital_release_date=_ymd(-1))
    sub = SimpleNamespace(
        media_id=media.media_id,
        sub_id="sub-1",
        followed=True,
        follow_reminded_air_date=None,
        follow_reminded_digital_release_date=None,
    )
    emitted = []

    async def fake_list():
        return [sub]

    async def fake_execution_snapshot(media_id, *, season_number=None):
        assert season_number is None
        return media

    async def fake_patch_by_sub_id(sub_id, patch):
        return None

    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.media_service.resolve_execution_snapshot", fake_execution_snapshot)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.event_service.emit_media", lambda event, meta=None: emitted.append((event, meta)))
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_command_service.patch_settings_by_sub_id", fake_patch_by_sub_id)

    await follow_reminder_service.run_once()

    assert [event.type for event, _ in emitted] == [EventTypes.FOLLOW_DIGITAL_RELEASED]


@pytest.mark.asyncio
async def test_follow_reminder_does_not_emit_old_tv_air_date(monkeypatch):
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:76479"),
        media_type=MediaType.tv,
        title="黑袍纠察队",
        year=2019,
        season_number=1,
        first_air_date="2019-07-25",
    )
    sub = SimpleNamespace(
        media_id=media.media_id,
        season_number=1,
        sub_id="sub-1",
        followed=True,
        follow_reminded_air_date=None,
    )
    emitted = []
    patches = []

    async def fake_list():
        return [sub]

    async def fake_execution_snapshot(media_id, *, season_number=None):
        assert season_number == 1
        return media

    async def fake_patch_by_sub_id(sub_id, patch):
        patches.append((sub_id, patch))

    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.media_service.resolve_execution_snapshot", fake_execution_snapshot)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.event_service.emit_media", lambda event, meta=None: emitted.append((event, meta)))
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_command_service.patch_settings_by_sub_id", fake_patch_by_sub_id)

    await follow_reminder_service.run_once(window_days=7)

    assert emitted == []
    assert patches == []
