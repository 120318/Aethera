from fastapi import APIRouter

from app.schemas.runtime.library_resource_list import (
    LibraryMediaServerLinkResolveRequest,
    LibraryMediaServerLinkResolveResponse,
)
from app.services.application.views.library.server_link import library_media_server_link_service

router = APIRouter()


@router.post("/media-server/link/resolve", response_model=LibraryMediaServerLinkResolveResponse)
async def resolve_library_media_server_link(
    body: LibraryMediaServerLinkResolveRequest,
) -> LibraryMediaServerLinkResolveResponse:
    link = await library_media_server_link_service.resolve(body)
    return LibraryMediaServerLinkResolveResponse(
        detail_url=link.detail_url,
        media_server_id=link.media_server_id,
        media_server_type=link.media_server_type,
    )
