from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import ServicesConfig
from app.services.config.settings_service import settings_service

router = APIRouter()


class ServicesConfigResponse(BaseModel):
    services: ServicesConfig


@router.get("/config/services", response_model=ServicesConfigResponse)
def get_services_config():
    return ServicesConfigResponse(services=settings_service.get_base_services_config())
