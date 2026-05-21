from types import SimpleNamespace

import pytest

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.audit.event_message_i18n import event_message_key, event_message_params
from app.services.application.workflows.follow_reminder import follow_reminder_service

pytestmark = pytest.mark.drift


def _movie(**updates) -> MediaFullInfo:
    payload = {
        "media_id": MediaID.parse("tmdb:movie:1"),
        "media_type": MediaType.movie,
        "title": "Sample",
        "year": 2026,
        "release_date": "2026-01-01",
        "theatrical_release_date": "2026-01-01",
        "digital_release_date": "2026-01-10",
    }
    payload.update(updates)
    return MediaFullInfo(**payload)


@pytest.mark.asyncio
async def test_follow_reminder_emits_movie_theatrical_digital_and_physical_events(monkeypatch):
    media = _movie(physical_release_date="2026-01-20")
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

    async def fake_info(media_id):
        return media

    async def fake_patch_by_sub_id(sub_id, patch):
        patches.append((sub_id, patch))

    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.media_service.cached_info", fake_info)
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
    assert [event_message_params(event, meta)["air_date"] for event, meta in emitted] == ["2026-01-01", "2026-01-10", "2026-01-20"]
    assert patches[0][1].follow_reminded_air_date == "2026-01-01"
    assert patches[0][1].follow_reminded_digital_release_date == "2026-01-10"
    assert patches[0][1].follow_reminded_physical_release_date == "2026-01-20"


@pytest.mark.asyncio
async def test_follow_reminder_emits_only_available_movie_release(monkeypatch):
    media = _movie(release_date=None, theatrical_release_date=None, digital_release_date="2026-01-10")
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

    async def fake_info(media_id):
        return media

    async def fake_patch_by_sub_id(sub_id, patch):
        return None

    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.media_service.cached_info", fake_info)
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.event_service.emit_media", lambda event, meta=None: emitted.append((event, meta)))
    monkeypatch.setattr("app.services.application.workflows.follow_reminder.service.subscription_command_service.patch_settings_by_sub_id", fake_patch_by_sub_id)

    await follow_reminder_service.run_once()

    assert [event.type for event, _ in emitted] == [EventTypes.FOLLOW_DIGITAL_RELEASED]
