from pydantic import BaseModel, Field

from app.schemas.domain.schedule import MediaScheduleSummary
from app.schemas.media_id import MediaID


class NextEpisodeToAir(BaseModel):
    season_number: int | None = None
    episode_number: int | None = None
    air_date: str | None = None
    title: str | None = None


class LibraryOverviewSnapshot(BaseModel):
    total_episodes: int = 0
    collected_count: int = 0
    collected_episodes: list[int] = Field(default_factory=list)
    downloading_count: int = 0
    downloading_episodes: list[int] = Field(default_factory=list)
    library_file_count: int = 0
    original_disc_package_count: int = 0
    original_disc_file_count: int = 0
    active_task_count: int = 0
    next_episode_to_air: NextEpisodeToAir | None = None
    schedule: MediaScheduleSummary | None = None


class LibraryOverviewResponse(LibraryOverviewSnapshot):
    media_id: MediaID
