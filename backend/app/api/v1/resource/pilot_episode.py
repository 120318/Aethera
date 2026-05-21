from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.services.application.workflows.subscription.pilot import pilot_download_application_service

router = APIRouter()


class PilotEpisodeRequest(BaseModel):
    target: MediaTarget
    directory_id: str
    sites: list[str] | None = None
    filters: SubscriptionFilters | None = None
    quality_profile_id: str | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] | None = None


@router.post("/pilot_episode", response_model=CommandResponse)
async def queue_pilot_episode(body: PilotEpisodeRequest) -> CommandResponse:
    command = await pilot_download_application_service.queue(
        target=body.target,
        directory_id=body.directory_id,
        filters=body.filters,
        quality_profile_id=body.quality_profile_id,
        sites=body.sites,
        unmatched_rules=body.unmatched_rules,
    )
    return CommandResponse(command=command)
