"""
textAPItext
"""
import logging

from app.schemas.domain.torrent_status import TorrentStatus
from app.services.domain.download import download_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class TorrentsProgressResponse(BaseModel):
    torrents: dict[str, TorrentStatus]  # task_id -> TorrentStatus


class ProgressRequest(BaseModel):
    task_ids: list[str]  # Internal note.


@router.post("/torrent_progress", response_model=TorrentsProgressResponse)
async def get_torrents_progress(body: ProgressRequest) -> TorrentsProgressResponse:
    """
    text（POST）.text JSON text：{ "task_ids": ["task_id1", "task_id2", ...] }
    identifiertext.
    """
    torrent_statuses = await download_service.get_torrent_status_by_task_ids(body.task_ids)
    return TorrentsProgressResponse(torrents=torrent_statuses)
