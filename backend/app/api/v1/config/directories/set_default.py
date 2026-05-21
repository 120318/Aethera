from app.api.v1.common_responses import OperationResponse
from app.schemas.domain.media_types import MediaType
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SetDefaultRequest(BaseModel):
    """Internal helper."""
    directory_id: str
    media_type: MediaType


@router.post("/config/directories/set-default", response_model=OperationResponse)
async def set_default_directory(request: SetDefaultRequest) -> OperationResponse:
    """text
    
    Args:
        request: identifiertext
        
    Returns:
        text
    """
    settings_service.set_default_directory(request.directory_id, request.media_type)
    bootstrap_service.recompute_status()
    return OperationResponse(
        ok=True,
        message_key="operationMessages.config.defaultDirectorySet",
        params={"media_type": request.media_type.value},
    )
