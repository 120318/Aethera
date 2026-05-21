from fastapi import APIRouter
from pydantic import BaseModel

from app.services.config.settings_service import settings_service
from app.services.platform.auth_provider_service import auth_provider_service

router = APIRouter()


class AuthProviderItem(BaseModel):
    id: str
    type: str
    name: str


class AuthProviderListResponse(BaseModel):
    providers: list[AuthProviderItem]


@router.get("/providers", response_model=AuthProviderListResponse)
async def list_auth_providers() -> AuthProviderListResponse:
    auth_addon = settings_service.get_addons_config().auth
    if not auth_addon.enabled:
        return AuthProviderListResponse(providers=[])
    configs = auth_addon.providers
    providers = auth_provider_service.list_provider_summaries(configs)
    items = [AuthProviderItem(id=item.id, type=item.type, name=item.name) for item in providers]
    return AuthProviderListResponse(providers=items)
