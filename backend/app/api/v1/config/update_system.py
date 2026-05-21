from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import DownloadConfig, LoggingConfig, SchedulerConfig, SystemConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from app.services.platform.runtime_restart_service import runtime_restart_service

router = APIRouter()


class UpdateConfigResponse(BaseModel):
    pass


class SchedulerSettingsRequest(BaseModel):
    scheduler: SchedulerConfig


class LoggingSettingsRequest(BaseModel):
    logging: LoggingConfig


class DownloadSettingsRequest(BaseModel):
    download: DownloadConfig


@router.post("/config/system", response_model=UpdateConfigResponse)
async def update_system_config(config: SystemConfig):
    settings_service.update_system_config(config)
    bootstrap_service.recompute_status()
    return UpdateConfigResponse()


@router.post("/config/system/scheduler", response_model=UpdateConfigResponse)
async def update_scheduler_config(config: SchedulerSettingsRequest):
    settings_service.update_scheduler_config(config.scheduler)
    return UpdateConfigResponse()


@router.post("/config/system/logging", response_model=UpdateConfigResponse)
async def update_logging_config(config: LoggingSettingsRequest):
    previous_level = settings_service.get_logging_config().logging.level
    settings_service.update_logging_config(config.logging)
    if previous_level != config.logging.level:
        runtime_restart_service.request_backend_restart()
    return UpdateConfigResponse()


@router.post("/config/system/download", response_model=UpdateConfigResponse)
async def update_download_config(config: DownloadSettingsRequest):
    settings_service.update_download_config(config.download)
    bootstrap_service.recompute_status()
    return UpdateConfigResponse()
