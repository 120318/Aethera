from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import AddonsConfig
from app.services.config.settings_service import settings_service

router = APIRouter()


class AddonsConfigResponse(BaseModel):
    addons: AddonsConfig


@router.get("", response_model=AddonsConfigResponse)
async def get_addons_config() -> AddonsConfigResponse:
    """Internal helper."""
    return AddonsConfigResponse(addons=settings_service.get_addons_config())

@router.post("", response_model=AddonsConfigResponse)
async def update_addons_config(addons_config: AddonsConfig) -> AddonsConfigResponse:
    """Internal helper."""
    updated = settings_service.update_addons_config(addons_config)
    return AddonsConfigResponse(addons=updated)
