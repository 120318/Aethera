from fastapi import APIRouter
from pydantic import BaseModel

from app.addons.registry import addon_service

router = APIRouter()


class AddonInfo(BaseModel):
    name: str
    enabled: bool
    subscribed_events: list[str]


class AddonListResponse(BaseModel):
    items: list[AddonInfo]


@router.get("/", response_model=AddonListResponse)
async def list_addons() -> AddonListResponse:
    items: list[AddonInfo] = []
    for addon in addon_service.list_addons():
        if not addon.exposed:
            continue
        enabled = addon_service.is_addon_enabled(addon.name)
        try:
            events = addon.subscribed_event_patterns() or []
        except (AttributeError, RuntimeError, ValueError):
            events = []
        items.append(AddonInfo(name=addon.name, enabled=enabled, subscribed_events=events))
    return AddonListResponse(items=items)
