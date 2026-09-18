from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import MediaIDParam
from app.schemas.media_id import MediaID
from app.services.domain.media import media_service

router = APIRouter()


class UpdateEpisodeCountOverrideRequest(BaseModel):
    season_number: int = Field(..., gt=0)
    episode_count_override: int | None = Field(default=None, gt=0)


class UpdateEpisodeCountOverrideResponse(BaseModel):
    media_id: MediaID
    season_number: int
    episode_count_override: int | None


@router.post("/episode-count-override", response_model=UpdateEpisodeCountOverrideResponse)
async def update_episode_count_override(
    body: UpdateEpisodeCountOverrideRequest,
    mid: MediaID = Depends(MediaIDParam),
) -> UpdateEpisodeCountOverrideResponse:
    await media_service.update_episode_count_override(
        mid,
        season_number=body.season_number,
        episode_count_override=body.episode_count_override,
    )
    return UpdateEpisodeCountOverrideResponse(
        media_id=mid,
        season_number=body.season_number,
        episode_count_override=body.episode_count_override,
    )
