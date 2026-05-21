from app.schemas.domain.action import ActionKind, ActionName, ActionStatus
from app.schemas.domain.media import MediaIdentity
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID, Provider
from app.services.audit.action_service import action_service


def test_action_persists_media_snapshot():
    media = MediaIdentity(
        media_id=MediaID(provider=Provider.tmdb, media_type=MediaType.movie, id="1109100"),
        title="长沙夜生活",
        year=2023,
    )

    action = action_service.create_action(
        kind=ActionKind.addon,
        action_name=ActionName.danmu_generate.value,
        status=ActionStatus.queued,
        media=media,
    )

    stored = action_service.get_action(action.id)

    assert stored is not None
    assert stored.media == media
    assert stored.media_id == media.media_id
