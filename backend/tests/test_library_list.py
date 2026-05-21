from unittest.mock import AsyncMock

import pytest

from app.api.v1.library.list import list_library_resources
from app.schemas.domain.command import (
    CommandRecord,
    CommandTargetType,
    CommandType,
    LibraryFileMediaServerSyncCommandRecordPayload,
)
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaFullInfo, MediaSeasonInfo, MediaSimpleInfo, MediaTarget
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_resource_list import LibraryResourceAction
from app.services.application.views.library.resource_list import LibraryResourceListService, _LibraryActionAvailabilityContext


def build_library_resource_list(files: list[LibraryFile]):
    return LibraryResourceListService()._build_resource_list(files, tags=[])


@pytest.mark.asyncio
async def test_library_list_uses_active_season_episode_count(monkeypatch):
    media_id = MediaID.parse("douban:tv:123")
    simple_media = MediaSimpleInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=2,
        episodes_count=24,
    )
    full_media = MediaFullInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=2,
        episodes_count=24,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=12),
            MediaSeasonInfo(season_number=2, episode_count=8),
        ],
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="/library/example-s02e01.mkv",
        file_name="example-s02e01.mkv",
        file_size=1024,
        created_at=1.0,
    )

    async def fake_simple_info(requested_media_id):
        assert requested_media_id == media_id
        return simple_media

    async def fake_cached_info(requested_media_id):
        assert requested_media_id == media_id
        return full_media

    async def fake_library_files(requested_media_id, season=None):
        assert requested_media_id == media_id
        assert season == 2
        return [library_file]

    async def fake_active_commands(*args, **kwargs):
        return []

    def fake_action_context(self, library_files, context):
        assert library_files == [library_file]
        return (False, False, False)

    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.simple_info", fake_simple_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.cached_info", fake_cached_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.library_service.get_files_by_media", fake_library_files)
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.command_service.list_media_active_commands",
        fake_active_commands,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.LibraryResourceListService._resolve_action_context",
        fake_action_context,
    )

    response = await list_library_resources(media_id, season_number=2)

    assert response.total_episodes == 8
    assert len(response.resources) == 1


@pytest.mark.asyncio
async def test_library_list_fetches_season_detail_when_cached_profile_is_missing(monkeypatch):
    media_id = MediaID.parse("douban:tv:123")
    simple_media = MediaSimpleInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=2,
        episodes_count=24,
    )
    full_media = MediaFullInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=2,
        episodes_count=24,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=12),
            MediaSeasonInfo(season_number=2, episode_count=8),
        ],
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="/library/example-s02e01.mkv",
        file_name="example-s02e01.mkv",
        file_size=1024,
        created_at=1.0,
    )

    async def fake_simple_info(requested_media_id):
        assert requested_media_id == media_id
        return simple_media

    async def fake_cached_info(requested_media_id):
        assert requested_media_id == media_id
        return None

    async def fake_info(requested_media_id, *, season_number=None):
        assert requested_media_id == media_id
        assert season_number == 2
        return full_media

    async def fake_library_files(requested_media_id, season=None):
        assert requested_media_id == media_id
        assert season == 2
        return [library_file]

    async def fake_active_commands(*args, **kwargs):
        return []

    def fake_action_context(self, library_files, context):
        assert library_files == [library_file]
        return (False, False, False)

    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.simple_info", fake_simple_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.cached_info", fake_cached_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.season_detail_for_library_view", fake_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.library_service.get_files_by_media", fake_library_files)
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.command_service.list_media_active_commands",
        fake_active_commands,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.LibraryResourceListService._resolve_action_context",
        fake_action_context,
    )

    response = await list_library_resources(media_id, season_number=2)

    assert response.total_episodes == 8
    assert len(response.resources) == 1


@pytest.mark.asyncio
async def test_library_list_uses_movie_media_for_danmu_actions(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    simple_media = MediaSimpleInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.movie,
        id=media_id.id,
        title="Test Movie",
        year=2026,
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="/library/test-movie.mkv",
        file_name="test-movie.mkv",
        file_size=1024,
        created_at=1.0,
    )

    async def fake_simple_info(requested_media_id):
        assert requested_media_id == media_id
        return simple_media

    async def fake_library_files(requested_media_id, season=None):
        assert requested_media_id == media_id
        assert season is None
        return [library_file]

    async def fake_active_commands(*args, **kwargs):
        return []

    async def fake_action_context(self, library_files, **context):
        assert library_files == [library_file]
        assert context["media_id"] == media_id
        assert context["season_number"] is None
        assert context["full_media"] is None
        return _LibraryActionAvailabilityContext(
            media_server_open_enabled_directory_ids=set(),
            media_server_sync_enabled_directory_ids=set(),
            danmu_enabled_directory_ids={"dir-1"},
            danmu_media_available=True,
        )

    monkeypatch.setattr("app.services.application.views.library.resource_list.media_service.simple_info", fake_simple_info)
    monkeypatch.setattr("app.services.application.views.library.resource_list.library_service.get_files_by_media", fake_library_files)
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.command_service.list_media_active_commands",
        fake_active_commands,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.LibraryResourceListService._build_action_availability_context",
        fake_action_context,
    )

    response = await list_library_resources(media_id)

    assert len(response.resources) == 1
    assert LibraryResourceAction.DANMU_GENERATE in response.resources[0].actions


@pytest.mark.asyncio
async def test_library_list_resolves_movie_danmu_actions_from_simple_media(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    service = LibraryResourceListService()
    files = [
        LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
            media_id=media_id,
            path="/library/test-movie.mkv",
            file_name="test-movie.mkv",
            file_size=1024,
            created_at=1.0,
        )
    ]

    monkeypatch.setattr("app.services.application.views.library.resource_list.settings_service.list_media_servers", lambda: [])
    monkeypatch.setattr("app.services.application.views.library.resource_list.settings_service.list_directories", lambda: [])
    monkeypatch.setattr("app.services.application.views.library.resource_list.settings_service.list_tags", lambda: [])
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.download_service.get_tasks_by_ids",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.danmu_application_service.config",
        lambda: type("DanmuConfig", (), {"enabled": True, "directory_ids": ["dir-1"], "providers": []})(),
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.danmu_source_resolver.media_with_fetchable_source",
        AsyncMock(return_value=MediaFullInfo(
            media_id=media_id,
            provider=media_id.provider,
            media_type=MediaType.movie,
            id=media_id.id,
            title="Test Movie",
            year=2026,
            vendors=[],
        )),
    )
    monkeypatch.setattr(
        "app.services.application.views.library.resource_list.danmu_source_resolver.has_fetchable_vendor",
        lambda _media, _config: True,
    )

    response = await service._build_response(
        media_id=media_id,
        active_season_number=None,
        total_episodes=0,
        full_media=None,
        active_commands=[],
        library_files=files,
    )

    assert LibraryResourceAction.DANMU_GENERATE in response.resources[0].actions


def test_library_list_groups_original_disc_internal_files():
    media_id = MediaID.parse("tmdb:movie:1")
    attrs = ResourceAttributes(resource_form="BluRay Disc", package_layout="BDMV", disc_number=1, disc_total=2)
    resources = build_library_resource_list([
        LibraryFile(
            id="file-cert",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)/Test.Movie.2024.BluRay.Disc/CERTIFICATE",
            file_name="id.bdmv",
            file_size=10,
            file_index=1,
            created_at=1.0,
            resource_attributes=attrs,
        ),
        LibraryFile(
            id="file-index",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)/Test.Movie.2024.BluRay.Disc/BDMV",
            file_name="index.bdmv",
            file_size=20,
            file_index=0,
            created_at=2.0,
            resource_attributes=attrs,
        ),
    ])

    assert len(resources) == 1
    assert resources[0].id == "file-index"
    assert resources[0].is_package is True
    assert resources[0].file_name == "Test.Movie.2024.BluRay.Disc"
    assert resources[0].directory == "/Movies/Test Movie (2024)"
    assert resources[0].package_root == "Movies/Test Movie (2024)/Test.Movie.2024.BluRay.Disc"
    assert resources[0].size == 30
    assert resources[0].attributes.resource_form == "BluRay Disc"
    assert resources[0].attributes.package_layout == "BDMV"
    assert resources[0].attributes.disc_number is None
    assert resources[0].attributes.disc_total == 1


def test_library_list_groups_multi_disc_original_disc_as_one_package():
    media_id = MediaID.parse("tmdb:tv:1")
    attrs = ResourceAttributes(resource_form="BluRay Disc", package_layout="BDMV", seasons=[1], episodes=[])
    resources = build_library_resource_list([
        LibraryFile(
            id="disc-1-index",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Shows/Test Show (2024)/Season 01/Test.Show.S01.BluRay/THE_SHOW_D1/BDMV",
            file_name="index.bdmv",
            file_size=20,
            file_index=0,
            created_at=1.0,
            resource_attributes=attrs,
        ),
        LibraryFile(
            id="disc-2-index",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Shows/Test Show (2024)/Season 01/Test.Show.S01.BluRay/THE_SHOW_D2/BDMV",
            file_name="index.bdmv",
            file_size=30,
            file_index=1,
            created_at=2.0,
            resource_attributes=attrs,
        ),
    ])

    assert len(resources) == 1
    assert resources[0].id == "disc-1-index"
    assert resources[0].is_package is True
    assert resources[0].file_name == "Test.Show.S01.BluRay"
    assert resources[0].directory == "/Shows/Test Show (2024)/Season 01"
    assert resources[0].package_root == "Shows/Test Show (2024)/Season 01/Test.Show.S01.BluRay"
    assert resources[0].file_count == 2
    assert resources[0].size == 50
    assert resources[0].attributes.disc_number is None
    assert resources[0].attributes.disc_total == 2


def test_library_list_marks_iso_as_single_file_package():
    media_id = MediaID.parse("tmdb:movie:1")
    attrs = ResourceAttributes(resource_form="BluRay Disc", package_layout="ISO")
    resources = build_library_resource_list([
        LibraryFile(
            id="file-iso",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)/Test.Movie.2024.BDISO",
            file_name="Test Movie.iso",
            file_size=30,
            file_index=0,
            created_at=1.0,
            resource_attributes=attrs,
        ),
    ])

    assert len(resources) == 1
    assert resources[0].id == "file-iso"
    assert resources[0].is_package is True
    assert resources[0].file_name == "Test.Movie.2024.BDISO"
    assert resources[0].file_count == 1
    assert resources[0].package_root == "Movies/Test Movie (2024)/Test.Movie.2024.BDISO"
    assert resources[0].attributes.disc_number is None
    assert resources[0].attributes.disc_total == 1


def test_library_list_action_states_follow_backend_capabilities():
    media_id = MediaID.parse("tmdb:movie:1")
    service = LibraryResourceListService()
    resource = build_library_resource_list([
        LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)",
            file_name="Test.Movie.2024.mkv",
            file_size=30,
            created_at=1.0,
        ),
    ])[0]

    updated = service._apply_action_states(resource, None, (True, True, False))

    assert updated.actions == [
        LibraryResourceAction.VIEW_DETAIL,
        LibraryResourceAction.DELETE,
        LibraryResourceAction.MEDIA_SERVER_OPEN,
        LibraryResourceAction.MEDIA_SERVER_SYNC,
    ]
    assert all(not state.loading for state in updated.action_states)


@pytest.mark.asyncio
async def test_library_list_resolves_actions_per_resource_file_set(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    service = LibraryResourceListService()
    files = [
        LibraryFile(
            id="file-sync",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)",
            file_name="Test.Movie.2024.Sync.mkv",
            file_size=30,
            created_at=2.0,
        ),
        LibraryFile(
            id="file-danmu",
            task_id="task-2",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)",
            file_name="Test.Movie.2024.Danmu.mkv",
            file_size=30,
            created_at=1.0,
        ),
    ]

    context = _LibraryActionAvailabilityContext(
        media_server_open_enabled_directory_ids={"dir-1"},
        media_server_sync_enabled_directory_ids={"dir-1"},
        danmu_enabled_directory_ids={"dir-2"},
        danmu_media_available=True,
    )

    resources = service._build_resource_list(files, tags=[])
    resource_files_map = service._build_resource_files_map(resources, files)
    context_map = await service._resolve_action_context_map(resources, resource_files_map, context)
    updated = [
        service._apply_action_states(resource, None, context_map[service._resource_target_id(resource)])
        for resource in resources
    ]
    actions_by_id = {resource.id: resource.actions for resource in updated}

    assert LibraryResourceAction.MEDIA_SERVER_OPEN in actions_by_id["file-sync"]
    assert LibraryResourceAction.MEDIA_SERVER_SYNC in actions_by_id["file-sync"]
    assert LibraryResourceAction.DANMU_GENERATE not in actions_by_id["file-sync"]
    assert LibraryResourceAction.MEDIA_SERVER_OPEN in actions_by_id["file-danmu"]
    assert LibraryResourceAction.MEDIA_SERVER_SYNC in actions_by_id["file-danmu"]
    assert LibraryResourceAction.DANMU_GENERATE not in actions_by_id["file-danmu"]


@pytest.mark.asyncio
async def test_library_list_resolves_package_actions_from_package_files(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    service = LibraryResourceListService()
    attrs = ResourceAttributes(resource_form="BluRay Disc", package_layout="BDMV")
    files = [
        LibraryFile(
            id="file-cert",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)/Test.Movie.2024.BluRay/CERTIFICATE",
            file_name="id.bdmv",
            file_size=10,
            file_index=1,
            created_at=1.0,
            resource_attributes=attrs,
        ),
        LibraryFile(
            id="file-index",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)/Test.Movie.2024.BluRay/BDMV",
            file_name="index.bdmv",
            file_size=20,
            file_index=0,
            created_at=2.0,
            resource_attributes=attrs,
        ),
    ]

    context = _LibraryActionAvailabilityContext(
        media_server_open_enabled_directory_ids={"dir-1"},
        media_server_sync_enabled_directory_ids={"dir-1"},
        danmu_enabled_directory_ids=set(),
        danmu_media_available=False,
    )

    resources = service._build_resource_list(files, tags=[])
    resource_files_map = service._build_resource_files_map(resources, files)
    package = resources[0]
    context_map = await service._resolve_action_context_map(resources, resource_files_map, context)
    updated = service._apply_action_states(package, None, context_map[service._resource_target_id(package)])

    assert package.is_package is True
    assert LibraryResourceAction.MEDIA_SERVER_OPEN in updated.actions
    assert LibraryResourceAction.MEDIA_SERVER_SYNC in updated.actions
    assert LibraryResourceAction.DANMU_GENERATE not in updated.actions


def test_library_list_action_states_mark_resource_busy_for_active_command():
    media_id = MediaID.parse("tmdb:movie:1")
    service = LibraryResourceListService()
    resource = build_library_resource_list([
        LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Movies/Test Movie (2024)",
            file_name="Test.Movie.2024.mkv",
            file_size=30,
            created_at=1.0,
        ),
    ])[0]
    command = CommandRecord(
        id="command-1",
        type=CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC,
        payload=LibraryFileMediaServerSyncCommandRecordPayload(
            file_id="file-1",
            target=MediaTarget(media_id=media_id),
        ),
        target_type=CommandTargetType.LIBRARY_FILE,
        target_id="file-1",
    )

    updated = service._apply_action_states(resource, command, (True, True, True))

    busy_states = [
        state for state in updated.action_states
        if state.action != LibraryResourceAction.VIEW_DETAIL
    ]
    assert busy_states
    assert all(state.loading for state in busy_states)
    assert all(state.disabled for state in busy_states)
    assert {state.active_command_id for state in busy_states} == {"command-1"}
