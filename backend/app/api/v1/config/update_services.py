from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.schemas.config import BrowseSource, DoubanConfig, ServicesConfig, TMDBConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service

router = APIRouter()


class UpdateConfigResponse(BaseModel):
    pass


@router.post("/config/services", response_model=UpdateConfigResponse)
async def update_services_config(config: ServicesConfig):
    settings_service.update_services_config(config)
    bootstrap_service.recompute_status()
    return UpdateConfigResponse()


@router.post("/config/services/tmdb", response_model=UpdateConfigResponse)
async def update_tmdb_config(config: TMDBConfig):
    settings_service.update_tmdb_config(config)
    bootstrap_service.recompute_status()
    return UpdateConfigResponse()


@router.post("/config/services/douban", response_model=UpdateConfigResponse)
async def update_douban_config(config: DoubanConfig):
    settings_service.update_douban_config(config)
    return UpdateConfigResponse()


@router.post("/config/services/browse-source", response_model=UpdateConfigResponse)
async def update_browse_source(source: BrowseSource = Body(...)):
    settings_service.update_browse_source(source)
    return UpdateConfigResponse()
