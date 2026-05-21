from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.resource.sites_support import list_available_sites
from app.schemas.integration.site_models import SiteInfo

router = APIRouter()


class SitesData(BaseModel):
    sites: list[SiteInfo]


class SitesResponse(BaseModel):
    data: SitesData


@router.get("/sites", response_model=SitesResponse)
async def get_available_sites() -> SitesResponse:
    """
    textPTtext
    """
    return SitesResponse(data=SitesData(sites=await list_available_sites()))
