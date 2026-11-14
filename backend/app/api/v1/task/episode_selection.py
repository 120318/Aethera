from fastapi import APIRouter

from app.schemas.domain.download import EpisodeSelectionUpdateRequest, EpisodeSelectionView
from app.services.domain.download import download_service

router = APIRouter()


@router.get("/{task_id}/episode-selection", response_model=EpisodeSelectionView)
async def get_task_episode_selection(task_id: str) -> EpisodeSelectionView:
    return await download_service.get_task_episode_selection(task_id)


@router.put("/{task_id}/episode-selection", response_model=EpisodeSelectionView)
async def update_task_episode_selection(
    task_id: str,
    body: EpisodeSelectionUpdateRequest,
) -> EpisodeSelectionView:
    return await download_service.update_task_episode_selection(task_id, body.selected_episodes)
