from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.runtime.settings_runtime import ObjectConfigSnapshot
from app.services.config.settings_service import settings_service

router = APIRouter()


class ConfigResponse(BaseModel):
    config: ObjectConfigSnapshot


@router.get("/config", response_model=ConfigResponse)
def get_config():
    return ConfigResponse(config=settings_service.get_object_config())
