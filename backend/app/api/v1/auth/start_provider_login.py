from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.schemas.exception.exceptions import AuthenticationProviderDisabledException, ExternalAuthNotEnabledException
from app.services.config.settings_service import settings_service
from app.services.platform.auth_service import auth_service
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.platform.external_auth_state_service import external_auth_state_service

router = APIRouter()


class StartProviderLoginRequest(BaseModel):
    next_path: str = "/discover"


class StartProviderLoginResponse(BaseModel):
    redirect_url: str


@router.post("/providers/{provider_id}/start", response_model=StartProviderLoginResponse)
async def start_provider_login(provider_id: str, body: StartProviderLoginRequest, request: Request, response: Response) -> StartProviderLoginResponse:
    auth_addon = settings_service.get_addons_config().auth
    if not auth_addon.enabled:
        raise ExternalAuthNotEnabledException()

    config = auth_provider_service.find_provider_config(auth_addon.providers, provider_id)
    if not config.enabled:
        raise AuthenticationProviderDisabledException()

    provider = auth_provider_service.get_provider(config.type)
    state = external_auth_state_service.create_state(provider_id, body.next_path)
    redirect_uri = str(request.url_for("handle_provider_callback", provider_id=provider_id))
    result = provider.build_authorize_redirect(config, redirect_uri, state.state, state.nonce, state.code_verifier)

    response.set_cookie(
        key=external_auth_state_service.COOKIE_NAME,
        value=external_auth_state_service.encode(state),
        httponly=True,
        samesite="lax",
        secure=auth_service.is_https_request(request),
        max_age=external_auth_state_service.TTL_SECONDS,
        path="/",
    )
    return StartProviderLoginResponse(redirect_url=result.redirect_url)
