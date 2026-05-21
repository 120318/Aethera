import os
import uuid

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.constants.event_types import EventTypes
from app.schemas.media_id import MediaID
from app.schemas.domain.event import EventEntityRef, EventLevel, MediaEventCreate
from app.schemas.domain.media import MediaIdentity
from app.services.audit.event_service import EventService


def test_emit_and_list_events_basic():
    svc = EventService()
    media_id = MediaID.parse(f"douban:movie:{uuid.uuid4().hex}")
    ev = svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_STARTED,
            level=EventLevel.info,
            message="created",
            media=MediaIdentity(media_id=media_id, title="text1", year=2024),
            task_id="t1",
            entities=[EventEntityRef(type="downloader", id="d1")],
        ),
    )
    assert ev is not None
    total, items = svc.list_events(media_id=media_id, limit=10, offset=0)
    assert total >= 1
    assert any(x.id == ev.id for x in items)


def test_emit_media_merges_default_and_explicit_message_params():
    svc = EventService()
    media_id = MediaID.parse(f"douban:movie:{uuid.uuid4().hex}")
    ev = svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_STARTED,
            level=EventLevel.info,
            media=MediaIdentity(media_id=media_id, title="text1", year=2024),
            message_params={"downloader_id": "d1"},
        ),
    )

    assert ev.message_params["title"] == "text1"
    assert ev.message_params["media_id"] == str(media_id)
    assert ev.message_params["downloader_id"] == "d1"


def test_list_events_filters():
    svc = EventService()
    media_id_1 = MediaID.parse(f"douban:movie:{uuid.uuid4().hex}")
    media_id_2 = MediaID.parse(f"douban:movie:{uuid.uuid4().hex}")
    svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_STARTED,
            message="hello",
            media=MediaIdentity(media_id=media_id_1, title="text1", year=2024),
        )
    )
    svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_COMPLETED,
            message="world",
            media=MediaIdentity(media_id=media_id_2, title="text2", year=2024),
        )
    )
    total, items = svc.list_events(media_id=media_id_1, limit=50)
    assert total == 1
    assert items[0].media_id == media_id_1


def test_list_events_filters_tv_seasons():
    svc = EventService()
    media_id = MediaID.parse(f"tmdb:tv:{uuid.uuid4().int % 100000000}")
    season_one_event = svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_STARTED,
            media=MediaIdentity(media_id=media_id, season_number=1, title="text1", year=2024),
        )
    )
    season_two_event = svc.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_COMPLETED,
            media=MediaIdentity(media_id=media_id, season_number=2, title="text1", year=2024),
        )
    )

    total, items = svc.list_events(media_id=media_id, season_number=1, limit=50)

    assert total == 1
    assert [item.id for item in items] == [season_one_event.id]
    assert items[0].media.season_number == 1
    assert season_two_event.id not in [item.id for item in items]
