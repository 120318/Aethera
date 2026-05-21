from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.media.external_mapping_tmdb import AttachTMDBMappingRequest, attach_tmdb_mapping
from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.schemas.domain.command import (
    CommandInitiator,
    CommandRecord,
    CommandStatus,
    CommandTargetType,
    CommandType,
    ProfileRefreshCommandRecordPayload,
)
from app.schemas.domain.media import MediaSimpleInfo, MediaTarget
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.persistence.media_external_mapping import MediaExternalMappingRecord
from app.services.application.workflows.media_external_mapping.service import (
    MediaExternalMappingApplicationService,
    MediaExternalMappingAttachCommandResult,
)
from app.services.domain.media.mapping import MediaExternalMappingService, TMDBMappingAttachResult


class FakeMappingRepo:
    def __init__(self, previous_mapping=None) -> None:
        self.previous_mapping = previous_mapping
        self.upserts = []
        self.removed = []

    def find_by_media_id(self, media_id):
        if self.previous_mapping and self.previous_mapping.media_id == media_id:
            return self.previous_mapping
        return None

    def find_by_media_id_and_season(self, media_id, season_number):
        if (
            self.previous_mapping
            and self.previous_mapping.media_id == media_id
            and self.previous_mapping.season_number == season_number
        ):
            return self.previous_mapping
        return None

    def find_by_douban_id_and_season(self, douban_id, media_type, season_number):
        if (
            self.previous_mapping
            and self.previous_mapping.douban_id == douban_id
            and self.previous_mapping.media_type == media_type
            and self.previous_mapping.season_number == season_number
        ):
            return self.previous_mapping
        return None

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def remove(self, media_id, season_number=None):
        self.removed.append((media_id, season_number))
        return True


class FakeIdentityRepo:
    def __init__(self) -> None:
        self.merges = []

    def merge_media_id(self, source_media_id, target_media_id):
        self.merges.append((source_media_id, target_media_id))


class FakeTMDBClient:
    def __init__(self, *, provider_id: int, imdb_id: str | None) -> None:
        self.provider_id = provider_id
        self.imdb_id = imdb_id

    async def get_details_with_fallback(self, tmdb_id, subject_type):
        return SimpleNamespace(provider_id=self.provider_id)

    async def get_external_ids(self, tmdb_id, subject_type):
        return SimpleNamespace(imdb_id=self.imdb_id)


def _config():
    return SimpleNamespace(api_key="test-key")


def _command(media_id: MediaID, command_id: str = "cmd-1") -> CommandRecord:
    season_number = 1 if media_id.media_type.value == "tv" else None
    target = MediaTarget(media_id=media_id, season_number=season_number)
    return CommandRecord(
        id=command_id,
        type=CommandType.PROFILE_REFRESH,
        status=CommandStatus.QUEUED,
        message="Sample",
        payload=ProfileRefreshCommandRecordPayload(target=target),
        initiator=CommandInitiator.SYSTEM,
        media_id=media_id,
        target=target,
        uniq_key=f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}",
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )


def _media(mid: MediaID, *, imdb_id="tt0499549", douban_id: str | None = None, season_number: int | None = None) -> MediaSimpleInfo:
    return MediaSimpleInfo(
        media_id=mid,
        title="Test Media",
        year=2026,
        media_type=mid.media_type,
        imdb_id=imdb_id,
        douban_id=douban_id,
        season_number=season_number,
    )


def _service(
    *,
    repo: FakeMappingRepo | None = None,
    provider_id: int,
    imdb_id: str | None,
    identity_repo: FakeIdentityRepo | None = None,
) -> MediaExternalMappingService:
    return MediaExternalMappingService(
        mapping_repo=repo or FakeMappingRepo(),
        identity_repo=identity_repo or FakeIdentityRepo(),
        tmdb_config_getter=_config,
        tmdb_client_factory=lambda _config: FakeTMDBClient(provider_id=provider_id, imdb_id=imdb_id),
    )


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_route_returns_refresh_command(monkeypatch):
    mid = MediaID.parse("tmdb:movie:19995")
    canonical_mid = MediaID.parse("tmdb:movie:12345")
    command = _command(mid)
    attach_mock = AsyncMock(return_value=MediaExternalMappingAttachCommandResult(media_id=canonical_mid, command=command))
    monkeypatch.setattr(
        "app.api.v1.media.external_mapping_tmdb.media_external_mapping_application_service.attach_tmdb_mapping",
        attach_mock,
    )

    response = await attach_tmdb_mapping(
        AttachTMDBMappingRequest(tmdb_id=12345),
        mid=mid,
    )

    assert response.command.id == "cmd-1"
    assert response.media_id == canonical_mid
    attach_mock.assert_awaited_once_with(mid, tmdb_id=12345, season_number=None, episode_count_override=None)


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_persists_tv_season_number():
    mid = MediaID.parse("tmdb:tv:19995")
    repo = FakeMappingRepo()
    service = _service(repo=repo, provider_id=12345, imdb_id="tt1234567")

    await service.attach_tmdb_mapping(
        _media(mid, douban_id="36513446", season_number=2),
        tmdb_id=12345,
        season_number=3,
    )

    assert repo.upserts[0]["season_number"] == 3
    assert repo.upserts[0]["media_id"] == MediaID.parse("tmdb:tv:12345")


def test_external_mapping_remove_requires_tv_season_number():
    repo = MediaExternalMappingRepository()
    mid = MediaID.parse("tmdb:tv:remove-season-scope")
    repo.upsert(
        media_id=mid,
        tmdb_id=12345,
        imdb_id="tt1234567",
        douban_id="douban-remove-season-scope-1",
        season_number=1,
    )
    repo.upsert(
        media_id=mid,
        tmdb_id=12345,
        imdb_id="tt1234567",
        douban_id="douban-remove-season-scope-2",
        season_number=2,
    )

    assert repo.remove(mid) is False
    assert repo.find_by_media_id_and_season(mid, 1) is not None
    assert repo.find_by_media_id_and_season(mid, 2) is not None

    assert repo.remove(mid, 1) is True
    assert repo.find_by_media_id_and_season(mid, 1) is None
    assert repo.find_by_media_id_and_season(mid, 2) is not None


def test_external_mapping_upsert_rebinds_douban_season_to_new_media_id():
    repo = MediaExternalMappingRepository()
    old_mid = MediaID.parse("tmdb:tv:111")
    new_mid = MediaID.parse("tmdb:tv:222")
    repo.upsert(
        media_id=old_mid,
        tmdb_id=111,
        imdb_id="tt1111111",
        douban_id="douban-rebind-season",
        season_number=2,
        episode_count_override=8,
    )

    repo.upsert(
        media_id=new_mid,
        tmdb_id=222,
        imdb_id="tt2222222",
        douban_id="douban-rebind-season",
        season_number=2,
        episode_count_override=10,
    )

    assert repo.find_by_media_id_and_season(old_mid, 2) is None
    rebound = repo.find_by_media_id_and_season(new_mid, 2)
    assert rebound is not None
    assert rebound.douban_id == "douban-rebind-season"
    assert rebound.tmdb_id == 222
    assert rebound.episode_count_override == 10


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_removes_previous_canonical_tmdb_alias_on_rebind():
    mid = MediaID.parse("douban:tv:36513446")
    old_canonical = MediaID.parse("tmdb:tv:111")
    new_canonical = MediaID.parse("tmdb:tv:222")
    previous_mapping = MediaExternalMappingRecord(
        source="douban",
        source_id="36513446",
        media_type="tv",
        media_id=old_canonical,
        tmdb_id=111,
        imdb_id="tt0499549",
        douban_id="36513446",
        season_number=2,
    )
    repo = FakeMappingRepo(previous_mapping)
    identity_repo = FakeIdentityRepo()
    service = _service(repo=repo, identity_repo=identity_repo, provider_id=222, imdb_id="tt2222222")

    result = await service.attach_tmdb_mapping(
        _media(mid, douban_id="36513446", season_number=2),
        tmdb_id=222,
    )
    service.finalize_tmdb_mapping_attach(result)

    assert repo.upserts[0]["media_id"] == new_canonical
    assert repo.removed == [(old_canonical, 2)]
    assert (mid, new_canonical) in identity_repo.merges
    assert (old_canonical, new_canonical) in identity_repo.merges


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_merges_old_tmdb_media_state_on_rebind():
    old_canonical = MediaID.parse("tmdb:tv:111")
    new_canonical = MediaID.parse("tmdb:tv:222")
    previous_mapping = MediaExternalMappingRecord(
        source="tmdb",
        source_id="111",
        media_type="tv",
        media_id=old_canonical,
        tmdb_id=111,
        imdb_id="tt0499549",
        douban_id="36513446",
        season_number=1,
    )
    repo = FakeMappingRepo(previous_mapping)
    identity_repo = FakeIdentityRepo()
    service = _service(repo=repo, identity_repo=identity_repo, provider_id=222, imdb_id="tt2222222")

    result = await service.attach_tmdb_mapping(
        _media(old_canonical, douban_id="36513446", season_number=1),
        tmdb_id=222,
    )
    service.finalize_tmdb_mapping_attach(result)

    assert repo.removed == [(old_canonical, 1)]
    assert identity_repo.merges == [(old_canonical, new_canonical)]


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_rolls_back_pending_mapping():
    mid = MediaID.parse("tmdb:movie:19995")
    repo = FakeMappingRepo()
    service = _service(
        repo=repo,
        provider_id=12345,
        imdb_id="tt1234567",
    )

    result = await service.attach_tmdb_mapping(_media(mid), tmdb_id=12345)
    service.rollback_tmdb_mapping_attach(result)

    assert (MediaID.parse("tmdb:movie:12345"), None) in repo.removed


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_rolls_back_only_target_tv_season():
    mid = MediaID.parse("tmdb:tv:19995")
    repo = FakeMappingRepo()
    service = _service(
        repo=repo,
        provider_id=12345,
        imdb_id="tt1234567",
    )

    result = await service.attach_tmdb_mapping(
        _media(mid, season_number=2),
        tmdb_id=12345,
    )
    service.rollback_tmdb_mapping_attach(result)

    assert repo.removed == [(MediaID.parse("tmdb:tv:12345"), 2)]


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_rolls_back_source_douban_tv_season():
    mid = MediaID.parse("douban:tv:36513446")
    repo = FakeMappingRepo()
    service = _service(
        repo=repo,
        provider_id=12345,
        imdb_id="tt1234567",
    )

    result = await service.attach_tmdb_mapping(
        _media(mid, douban_id="36513446", season_number=2),
        tmdb_id=12345,
    )
    service.rollback_tmdb_mapping_attach(result)

    assert repo.removed == [
        (MediaID.parse("tmdb:tv:12345"), 2),
        (MediaID.parse("douban:tv:36513446"), 2),
    ]


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_keeps_existing_imdb_id_when_tmdb_external_ids_missing():
    mid = MediaID.parse("douban:movie:36513446")
    repo = FakeMappingRepo()
    service = _service(repo=repo, provider_id=12345, imdb_id=None)

    await service.attach_tmdb_mapping(
        _media(mid, imdb_id="tt0499549", douban_id="36513446"),
        tmdb_id=12345,
    )

    assert repo.upserts[0]["imdb_id"] == "tt0499549"


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_uses_profile_refresh_command_service_force_requeue(monkeypatch):
    mid = MediaID.parse("tmdb:movie:19995")
    canonical_mid = MediaID.parse("tmdb:movie:12345")
    enqueue_mock = AsyncMock(side_effect=lambda media_id, **_: _command(media_id, "cmd-force-requeue"))
    monkeypatch.setattr("app.services.application.workflows.media_external_mapping.service.profile_refresh_command_service.enqueue", enqueue_mock)
    monkeypatch.setattr("app.services.application.workflows.media_external_mapping.service.media_service.simple_info", AsyncMock(return_value=_media(mid)))
    mapping_service = Mock()
    mapping_service.attach_tmdb_mapping = AsyncMock(return_value=TMDBMappingAttachResult(canonical_media_id=canonical_mid, source_media_id=mid))
    mapping_service.finalize_tmdb_mapping_attach = Mock()
    mapping_service.rollback_tmdb_mapping_attach = Mock()
    service = MediaExternalMappingApplicationService(mapping_service=mapping_service)

    result = await service.attach_tmdb_mapping(mid, tmdb_id=12345)

    assert result.media_id == canonical_mid
    assert result.command.id == "cmd-force-requeue"
    enqueue_mock.assert_awaited_once_with(
        canonical_mid,
        season_number=None,
        initiator=CommandInitiator.SYSTEM,
        force_requeue=True,
    )
    mapping_service.finalize_tmdb_mapping_attach.assert_called_once()


@pytest.mark.asyncio
async def test_attach_tmdb_mapping_application_keeps_requested_tv_season(monkeypatch):
    mid = MediaID.parse("tmdb:tv:19995")
    canonical_mid = MediaID.parse("tmdb:tv:12345")
    enqueue_mock = AsyncMock(side_effect=lambda media_id, **_: _command(media_id, "cmd-season"))
    apply_snapshot_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.workflows.media_external_mapping.service.profile_refresh_command_service.enqueue", enqueue_mock)
    monkeypatch.setattr(
        "app.services.application.workflows.media_external_mapping.service.media_service.simple_info",
        AsyncMock(return_value=_media(mid, season_number=2)),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.media_external_mapping.service.media_service.apply_source_mapping_snapshot",
        apply_snapshot_mock,
    )
    mapping_service = Mock()
    mapping_service.attach_tmdb_mapping = AsyncMock(return_value=TMDBMappingAttachResult(canonical_media_id=canonical_mid, source_media_id=mid))
    mapping_service.finalize_tmdb_mapping_attach = Mock()
    mapping_service.rollback_tmdb_mapping_attach = Mock()
    service = MediaExternalMappingApplicationService(mapping_service=mapping_service)

    await service.attach_tmdb_mapping(mid, tmdb_id=12345, season_number=3, episode_count_override=8)

    mapping_service.attach_tmdb_mapping.assert_awaited_once_with(
        _media(mid, season_number=2),
        tmdb_id=12345,
        season_number=3,
        episode_count_override=8,
    )
    enqueue_mock.assert_awaited_once_with(
        canonical_mid,
        season_number=3,
        initiator=CommandInitiator.SYSTEM,
        force_requeue=True,
    )
    apply_snapshot_mock.assert_awaited_once_with(
        canonical_mid,
        season_number=3,
        douban_id=None,
        episode_count_override=8,
    )
