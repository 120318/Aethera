import logging

from app.api.v1.common_responses import OperationResponse
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from app.schemas.exception import ConfigurationException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete("/config/templates/{template_id}", response_model=OperationResponse)
async def delete_template(template_id: str) -> OperationResponse:
    """text
    
    Args:
        template_id: identifier
        
    Returns:
        text
    """
    settings_service.delete_naming_template(template_id)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True, message_key="operationMessages.config.templateDeleted")
