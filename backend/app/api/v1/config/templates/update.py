import logging

from app.schemas.config import NamingTemplateConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.exception import ConfigurationException

logger = logging.getLogger(__name__)
router = APIRouter()


class TemplateUpdateRequest(BaseModel):
    """Internal helper."""
    template: NamingTemplateConfig


class TemplateSingleResponse(BaseModel):
    """Internal helper."""
    template: NamingTemplateConfig


@router.put("/config/templates", response_model=TemplateSingleResponse)
async def update_template(request: TemplateUpdateRequest):
    """text
    
    Args:
        request: text
        
    Returns:
        text
    """
    template = settings_service.update_naming_template(request.template)
    bootstrap_service.recompute_status()
    return TemplateSingleResponse(template=template)
