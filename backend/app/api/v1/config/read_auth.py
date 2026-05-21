from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import AuthConfig
from app.services.config.settings_service import settings_service

router = APIRouter()


class AuthConfigResponse(BaseModel):
    auth: AuthConfig


@router.get("/config/auth", response_model=AuthConfigResponse)
def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(auth=settings_service.get_base_auth_config())
