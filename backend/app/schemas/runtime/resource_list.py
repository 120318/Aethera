from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID

logger = logging.getLogger(__name__)


class EpisodeStatus(str, Enum):
    pending = "pending"
    downloading = "downloading"
    paused = "paused"
    processing = "processing"
    completed = "completed"
    archived = "archived"
    error = "error"


class EpisodeInfo(BaseModel):
    episode: int
    status: EpisodeStatus
    task_ids: list[str] = Field(default_factory=list)


class SeasonInfo(BaseModel):
    season: int
    episodes: list[EpisodeInfo]


class ResourceListResponse(BaseModel):
    media_id: MediaID
    tasks: list[TaskData] = Field(default_factory=list)
    seasons: list[SeasonInfo]


def map_task_status_to_episode_status(task_status: TaskStatus) -> EpisodeStatus:
    status_mapping = {
        "pending": EpisodeStatus.pending,
        "downloading": EpisodeStatus.downloading,
        "paused": EpisodeStatus.paused,
        "finished": EpisodeStatus.processing,
        "transferring": EpisodeStatus.processing,
        "completed": EpisodeStatus.completed,
        "error": EpisodeStatus.error,
        "partial_missing": EpisodeStatus.error,
        "seeding_absent": EpisodeStatus.completed,
        "file_missing": EpisodeStatus.error,
        "void": EpisodeStatus.error,
        "archived": EpisodeStatus.archived,
    }

    key = task_status.value.lower()
    if key in status_mapping:
        return status_mapping[key]

    logger.warning("Unknown task status '%s', mapping to pending", task_status.value)
    return EpisodeStatus.pending


def resolve_episode_status(
    task: TaskData,
    season_num: int,
    episode_num: int,
    existing_episode_keys: set[tuple[int, int]],
    media_has_primary_library_files: bool,
) -> EpisodeStatus:
    if task.status in {TaskStatus.PARTIAL_MISSING, TaskStatus.SEEDING_ABSENT}:
        if task.media_id.media_type == MediaType.movie:
            return EpisodeStatus.completed if media_has_primary_library_files else EpisodeStatus.error
        return EpisodeStatus.completed if (season_num, episode_num) in existing_episode_keys else EpisodeStatus.error
    return map_task_status_to_episode_status(task.status)
