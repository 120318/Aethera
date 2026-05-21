import logging

from app.api.v1.common_responses import OperationResponse
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.exception import ConfigurationException

logger = logging.getLogger(__name__)
router = APIRouter()


class SetDefaultTemplateRequest(BaseModel):
    """Internal helper."""
    template_id: str


class ClearDefaultTemplateRequest(BaseModel):
    template_type: str


@router.post("/config/templates/set-default", response_model=OperationResponse)
async def set_default_template(request: SetDefaultTemplateRequest) -> OperationResponse:
    """text
    
    Args:
        request: identifiertext
        
    Returns:
        text
    """
    settings_service.set_default_naming_template(request.template_id)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True, message_key="operationMessages.config.defaultTemplateSet")


@router.post("/config/templates/clear-default", response_model=OperationResponse)
async def clear_default_template(request: ClearDefaultTemplateRequest) -> OperationResponse:
    settings_service.clear_default_naming_template(request.template_type)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True, message_key="operationMessages.config.defaultTemplateCleared")
