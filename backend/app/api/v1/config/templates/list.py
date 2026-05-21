import logging

from app.schemas.config import NamingTemplateConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class TemplateListResponse(BaseModel):
    """Internal helper."""
    templates: list[NamingTemplateConfig]


@router.get("/config/templates", response_model=TemplateListResponse)
async def list_templates():
    """text
    
    Returns:
        text
    """
    return TemplateListResponse(templates=settings_service.list_naming_templates())
