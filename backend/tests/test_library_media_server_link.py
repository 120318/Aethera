import pytest

from app.schemas.config import DirectoryConfig, JellyfinConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_server_link import MediaServerDetailLink
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_resource_list import (
    LibraryMediaServerLinkResolveRequest,
    LibraryMediaServerTarget,
)
from app.services.application.views.library.server_link import LibraryMediaServerLinkService


def _request(media_id: MediaID, *, package_root: str = "") -> LibraryMediaServerLinkResolveRequest:
    return LibraryMediaServerLinkResolveRequest(
        file_id="file-1",
        target=LibraryMediaServerTarget(media_id=media_id),
        package_root=package_root,
    )


@pytest.mark.asyncio
async def test_library_media_server_link_resolves_bound_media_server_link(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="Movies/Test Movie (2026)",
        file_name="Test.Movie.2026.mkv",
        file_size=100,
        created_at=1.0,
    )
    media_server = JellyfinConfig(id="server-1", name="Jellyfin", url="http://jellyfin", api_key="token")

    async def fake_find_file(file_id):
        assert file_id == "file-1"
        return library_file

    async def fake_resolve_link(server, media_path):
        assert server == media_server
        assert media_path.endswith("/Movies/Test Movie (2026)/Test.Movie.2026.mkv")
        return MediaServerDetailLink(
            media_server_id="server-1",
            media_server_type="jellyfin",
            detail_url="http://jellyfin/web/index.html#!/details?id=item-1",
        )

    monkeypatch.setattr(
        "app.services.application.views.library.server_link.library_service.find_file_by_id",
        fake_find_file,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.server_link.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            media_type=MediaType.movie,
            media_server_id="server-1",
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.library.server_link.settings_service.list_media_servers",
        lambda: [media_server],
    )
    monkeypatch.setattr(
        "app.services.application.views.library.server_link.media_server_gateway.resolve_detail_link",
        fake_resolve_link,
    )

    result = await LibraryMediaServerLinkService().resolve(_request(media_id))

    assert result.detail_url == "http://jellyfin/web/index.html#!/details?id=item-1"
    assert result.media_server_type == "jellyfin"


@pytest.mark.asyncio
async def test_library_media_server_link_rejects_unbound_resource(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="Movies/Test Movie (2026)",
        file_name="Test.Movie.2026.mkv",
        created_at=1.0,
    )

    async def fake_find_file(file_id):
        assert file_id == "file-1"
        return library_file

    monkeypatch.setattr(
        "app.services.application.views.library.server_link.library_service.find_file_by_id",
        fake_find_file,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.server_link.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(id=directory_id, media_type=MediaType.movie, media_server_id=None),
    )

    with pytest.raises(InvalidRequestException) as exc:
        await LibraryMediaServerLinkService().resolve(_request(media_id))

    assert exc.value.message_key == "backendErrors.mediaServerLinkUnavailable"

