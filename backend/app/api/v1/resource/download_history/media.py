"""
textAPItext
"""

from app.schemas.media_id import MediaID
from app.schemas.domain.torrent_status import TorrentStatus
from app.services.domain.download import download_service
from app.api.deps import MediaIDPath
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class HistoryTorrent(BaseModel):
    id: str
    name: str
    size: int | None = None
    progress: float
    state: str
    category: str | None = None
    dlspeed: int | None = None
    eta: int | None = None


class MediaHistoryResponse(BaseModel):
    status: str
    message_key: str
    media_id: MediaID
    torrents: list[HistoryTorrent]


@router.get("/media/{media_id}", response_model=MediaHistoryResponse)
async def get_media_download_history(media_id: MediaID = Depends(MediaIDPath)) -> MediaHistoryResponse:
    tasks = await download_service.get_tasks(media_id=media_id)
    task_ids = [task.id for task in tasks]
    statuses = await download_service.get_torrent_status_by_task_ids(task_ids)

    result_torrents: list[HistoryTorrent] = []
    for task in tasks:
        if task.id not in statuses:
            continue

        status: TorrentStatus = statuses[task.id]
        size_value = task.metadata.size if task.metadata and task.metadata.size else status.size
        name_value = status.name or (task.metadata.name if task.metadata else "")

        result_torrents.append(
            HistoryTorrent(
                id=task.torrent_hash,
                name=name_value,
                size=size_value,
                progress=status.progress,
                state=status.state,
                category=status.category,
                dlspeed=status.download_speed,
                eta=status.eta,
            )
        )

    return MediaHistoryResponse(
        status="ok",
        message_key="operationMessages.downloadHistory.retrieved",
        media_id=media_id,
        torrents=result_torrents,
    )
