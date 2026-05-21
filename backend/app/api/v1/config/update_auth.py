from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.services.config.settings_service import settings_service
from app.services.platform.auth_service import auth_service

router = APIRouter()


class UpdateConfigResponse(BaseModel):
    pass


class AuthSettingsRequest(BaseModel):
    enabled: bool = False
    session_ttl_seconds: int = Field(default=86400, ge=0)


@router.post("/config/auth", response_model=UpdateConfigResponse)
async def update_auth_config(body: AuthSettingsRequest, request: Request, response: Response):
    settings_service.update_auth_config(body.enabled, body.session_ttl_seconds)
    current_session = auth_service.current_session(request)
    if current_session is not None:
        response.set_cookie(
            key=auth_service.COOKIE_NAME,
            value=current_session.token,
            httponly=True,
            samesite="lax",
            secure=auth_service.is_https_request(request),
            max_age=auth_service.get_session_cookie_max_age_seconds(),
            path="/",
        )
    return UpdateConfigResponse()
