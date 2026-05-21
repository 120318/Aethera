from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import LoggingConfig, SchedulerConfig, SystemConfig
from app.services.config.settings_service import settings_service

router = APIRouter()


class SystemConfigResponse(BaseModel):
    system: SystemConfig


class LoggingConfigResponse(BaseModel):
    logging: LoggingConfig


class SchedulerConfigResponse(BaseModel):
    scheduler: SchedulerConfig


@router.get("/config/system", response_model=SystemConfigResponse)
def get_system_config():
    return SystemConfigResponse(system=settings_service.get_base_system_config())


@router.get("/config/system/logging", response_model=LoggingConfigResponse)
def get_logging_config() -> LoggingConfigResponse:
    system_config = settings_service.get_logging_config()
    return LoggingConfigResponse(logging=system_config.logging)


@router.get("/config/system/scheduler", response_model=SchedulerConfigResponse)
def get_scheduler_config() -> SchedulerConfigResponse:
    return SchedulerConfigResponse(scheduler=settings_service.get_scheduler_config())
