from app.api.v1.common_responses import OperationResponse
from app.schemas.exception import ConfigurationException
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter

router = APIRouter()


@router.delete("/config/directories/delete/{directory_id}", response_model=OperationResponse)
async def delete_directory(directory_id: str) -> OperationResponse:
    """text
    
    Args:
        directory_id: identifier
        
    Returns:
        text
    """
    settings_service.delete_directory(directory_id)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True, message_key="operationMessages.config.directoryDeleted")
