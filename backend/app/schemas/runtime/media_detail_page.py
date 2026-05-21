from pydantic import BaseModel

from app.schemas.domain.command import CommandRecord
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_download_config import MediaDownloadConfigView
from app.schemas.domain.media_subscription_state import MediaSubscriptionStateView
from app.schemas.runtime.media_detail_overview import MediaDetailOverviewResponse
from app.schemas.runtime.task_view import TaskViewItem


class MediaDetailPageTabData(BaseModel):
    tasks: list[TaskViewItem] | None = None


class MediaDetailPageResponse(BaseModel):
    media: MediaFullInfo
    effective_season_number: int | None = None
    overview: MediaDetailOverviewResponse
    subscription: MediaSubscriptionStateView
    download_config: MediaDownloadConfigView
    active_commands: list[CommandRecord]
    tab_data: MediaDetailPageTabData
