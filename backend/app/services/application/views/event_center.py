import asyncio

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.event import EventCenterBellState, EventCenterDownload, EventCenterResponse
from app.services.audit.event_service import event_service
from app.services.domain.download import download_service


ACTIVE_DOWNLOAD_STATUSES = [
    TaskStatus.PENDING,
    TaskStatus.DOWNLOADING,
    TaskStatus.PAUSED,
]
RUNNING_DOWNLOAD_STATUSES = [
    TaskStatus.PENDING,
    TaskStatus.DOWNLOADING,
]
EVENT_CENTER_DOWNLOAD_LIMIT = 50


class EventCenterViewService:
    @staticmethod
    def _download_title(task: TaskData) -> str:
        context = task.context
        search_result = context.search_result if context else None
        if search_result and search_result.title:
            return search_result.title
        if context and context.resource_title:
            return context.resource_title
        if task.metadata and task.metadata.name:
            return task.metadata.name
        if context and context.media:
            return context.media.title
        return task.id

    async def get_center(self) -> EventCenterResponse:
        center = event_service.get_center()
        tasks, active_download_count = await asyncio.gather(
            download_service.get_tasks(
                status=ACTIVE_DOWNLOAD_STATUSES,
                limit=EVENT_CENTER_DOWNLOAD_LIMIT,
            ),
            download_service.count_tasks(status=RUNNING_DOWNLOAD_STATUSES),
        )
        center.active_downloads = [
            EventCenterDownload(
                id=task.id,
                status=task.status,
                progress=task.progress,
                title=self._download_title(task),
                media=task.context.media if task.context else None,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task in tasks
        ]
        center.summary.active_download_count = active_download_count
        if center.summary.bell_state == EventCenterBellState.idle and active_download_count:
            center.summary.bell_state = EventCenterBellState.running
        return center


event_center_view_service = EventCenterViewService()
