from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.media import MediaTarget
from app.services.application.workflows.subscription.pilot import pilot_download_application_service

router = APIRouter()


class PilotEpisodeRequest(BaseModel):
    target: MediaTarget


@router.post("/pilot_episode", response_model=CommandResponse)
async def queue_pilot_episode(body: PilotEpisodeRequest) -> CommandResponse:
    command = await pilot_download_application_service.queue(
        target=body.target,
    )
    return CommandResponse(command=command)
