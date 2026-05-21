from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandType,
    DirectoryIntegrityScanCommandRequestPayload,
    DirectoryIntegrityRepairCommandRequestPayload,
)
from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityPoliciesResponse,
    DirectoryIntegrityPoliciesUpdateRequest,
    DirectoryIntegrityRepairRequest,
    DirectoryIntegrityResult,
)
from app.services.application.commands.service import command_service
from app.services.application.workflows.directory_integrity import directory_integrity_service
from app.services.config.settings_service import settings_service

router = APIRouter()


class DirectoryIntegrityLatestResponse(BaseModel):
    result: DirectoryIntegrityResult | None = None


@router.get("/config/directories/integrity/latest", response_model=DirectoryIntegrityLatestResponse)
async def get_latest_directory_integrity() -> DirectoryIntegrityLatestResponse:
    return DirectoryIntegrityLatestResponse(result=await directory_integrity_service.latest())


@router.post("/config/directories/integrity/scan", response_model=CommandResponse)
async def scan_directory_integrity(body: DirectoryIntegrityScanCommandRequestPayload | None = None) -> CommandResponse:
    payload = body or DirectoryIntegrityScanCommandRequestPayload()
    command = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_SCAN,
            initiator=CommandInitiator.MANUAL,
            payload=payload,
        )
    )
    return CommandResponse(command=command)


@router.get("/config/directories/integrity/policies", response_model=DirectoryIntegrityPoliciesResponse)
async def get_directory_integrity_policies() -> DirectoryIntegrityPoliciesResponse:
    directories = [
        {
            "id": directory.id,
            "name": directory.name,
            "media_type": directory.media_type,
            "enabled": directory.enabled,
        }
        for directory in settings_service.list_directories()
    ]
    return DirectoryIntegrityPoliciesResponse(
        directories=directories,
        policies=settings_service.list_directory_integrity_policies(),
    )


@router.put("/config/directories/integrity/policies", response_model=DirectoryIntegrityPoliciesResponse)
async def update_directory_integrity_policies(
    body: DirectoryIntegrityPoliciesUpdateRequest,
) -> DirectoryIntegrityPoliciesResponse:
    policies = settings_service.update_directory_integrity_policies(body.policies)
    directories = [
        {
            "id": directory.id,
            "name": directory.name,
            "media_type": directory.media_type,
            "enabled": directory.enabled,
        }
        for directory in settings_service.list_directories()
    ]
    return DirectoryIntegrityPoliciesResponse(directories=directories, policies=policies)


@router.post("/config/directories/integrity/repair", response_model=CommandResponse)
async def repair_directory_integrity(body: DirectoryIntegrityRepairRequest) -> CommandResponse:
    item_ids = list(body.item_ids or [])
    command: CommandRecord | None = None
    for item_id in item_ids:
        command = await command_service.create_command(
            CommandCreateRequest(
                type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
                initiator=CommandInitiator.MANUAL,
                payload=DirectoryIntegrityRepairCommandRequestPayload(
                    scan_id=body.scan_id,
                    item_ids=[item_id],
                ),
            )
        )
    if command is None:
        command = await command_service.create_command(
            CommandCreateRequest(
                type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
                initiator=CommandInitiator.MANUAL,
                payload=DirectoryIntegrityRepairCommandRequestPayload(
                    scan_id=body.scan_id,
                    item_ids=[],
                ),
            )
        )
    return CommandResponse(command=command)
