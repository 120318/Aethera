from fastapi import APIRouter

from app.schemas.domain.download import EpisodeSelectionPreviewRequest, EpisodeSelectionView
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.application.workflows.resource_search import resource_search_service
from app.services.domain.download.episode_selection import available_episodes
from app.services.domain.resource.torrent_metadata import fetch_torrent_payload

router = APIRouter()


@router.post("/episode-selection/preview", response_model=EpisodeSelectionView)
async def preview_episode_selection(body: EpisodeSelectionPreviewRequest) -> EpisodeSelectionView:
    if body.media.media_type != MediaType.tv:
        return EpisodeSelectionView()
    result = resource_search_service.get_by_result_id(body.result_id)
    if not result:
        raise ResourceNotFoundException("backendErrors.resultIdInvalidOrExpired")
    payload = await fetch_torrent_payload(result)
    episodes = available_episodes(payload.metadata, body.media.season_number)
    return EpisodeSelectionView(
        selectable=bool(episodes),
        available_episodes=episodes,
        selected_episodes=episodes,
        episode_count=body.media.episodes_count,
    )
