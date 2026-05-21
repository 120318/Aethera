import logging

from app.schemas.config import NamingTemplateConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.exception import ConfigurationException, ServiceTypeException

logger = logging.getLogger(__name__)
router = APIRouter()


class TemplateAddRequest(BaseModel):
    """Internal helper."""
    template: NamingTemplateConfig


class TemplateSingleResponse(BaseModel):
    """Internal helper."""
    template: NamingTemplateConfig


@router.post("/config/templates", response_model=TemplateSingleResponse)
async def add_template(request: TemplateAddRequest):
    """text
    
    Args:
        request: text
        
    Returns:
        text
    """
    if request.template.type not in ["movie", "tv"]:
        raise ServiceTypeException(service_type=request.template.type)
    template = settings_service.create_naming_template(request.template)
    bootstrap_service.recompute_status()
    return TemplateSingleResponse(template=template)
