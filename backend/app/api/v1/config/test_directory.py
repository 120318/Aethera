from fastapi import APIRouter
from pydantic import BaseModel

from app.services.config.settings_service import settings_service

router = APIRouter()


class DirectoryTestRequest(BaseModel):
    """Internal helper."""
    path: str


class DirectoryTestResponse(BaseModel):
    """Internal helper."""
    permissions: dict[str, bool]


@router.post("/config/test-directory", response_model=DirectoryTestResponse)
async def test_directory(request: DirectoryTestRequest):
    """text
    
    Args:
        request: text
        
    Returns:
        text
    """
    permissions = settings_service.check_directory_permissions(request.path)
    return DirectoryTestResponse(permissions=permissions)
