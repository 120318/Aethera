from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.clients.rtorrent import RTorrentClient
from app.schemas.config import RTorrentConfig
from app.schemas.domain.download import DownloadInfoLookupStatus
from app.schemas.domain.torrent_status import TorrentState

pytestmark = [pytest.mark.drift]


class FakeRTorrentClient(RTorrentClient):
    def __init__(self):
        super().__init__(RTorrentConfig(id="rt", name="rt", url="http://rtorrent/RPC2"))
        self.calls = []
        self.hashing = 0
        self.complete = 0

    async def _rpc(self, method, params=()):
        self.calls.append((method, params))
        if method == "system.listMethods":
            return ["d.multicall2"]
        if method == "d.multicall2":
            return [
                [
                    "ABC",
                    "Movie",
                    100,
                    25,
                    "/remote/downloads",
                    "/remote/downloads/Movie",
                    10,
                    2,
                    1500,
                    self.complete,
                    1,
                    1,
                    int(datetime(2024, 1, 1).timestamp()),
                    75,
                    self.hashing,
                ]
            ]
        if method == "f.multicall":
            return [["Movie.mkv", 100, 3, 4, 1]]
        if method == "t.multicall":
            return [["https://tracker", 0, 1, 0]]
        return 0


@pytest.mark.asyncio
async def test_rtorrent_maps_torrent_status_and_files():
    client = FakeRTorrentClient()

    statuses = await client.get_torrents(["abc"])
    files = await client.get_torrent_files("abc")
    trackers = await client.get_torrent_trackers("abc")

    assert len(statuses) == 1
    assert statuses[0].hash == "abc"
    assert statuses[0].progress == 0.75
    assert statuses[0].state == TorrentState.DOWNLOADING
    assert statuses[0].ratio == 1.5
    assert files and files[0].progress == 0.75
    assert files[0].is_selected is True
    assert trackers == [{"msg": "tracker disabled", "message": "tracker disabled"}]


def test_rtorrent_maps_completed_stopped_torrent_as_paused():
    client = FakeRTorrentClient()
    row = client._to_torrent_row(
        [
            "ABC",
            "Movie",
            100,
            0,
            "/remote/downloads",
            "/remote/downloads/Movie",
            0,
            0,
            1500,
            1,
            0,
            0,
            int(datetime(2024, 1, 1).timestamp()),
            100,
            0,
        ]
    )

    assert client._torrent_state(row) == TorrentState.PAUSED


@pytest.mark.asyncio
@pytest.mark.parametrize("hashing", [1, 2, 3])
@pytest.mark.parametrize("complete", [0, 1])
async def test_rtorrent_reports_pending_and_active_hash_checks_before_download_state(hashing, complete):
    client = FakeRTorrentClient()
    client.hashing = hashing
    client.complete = complete
    statuses = await client.get_torrents(["abc"])
    info = await client.get_torrent_info("abc")
    assert statuses[0].state == TorrentState.CHECKING
    assert statuses[0].completion_on is None
    assert info.state == TorrentState.CHECKING.value
    assert info.completion_on is None
    assert all("d.hashing=" in params for method, params in client.calls if method == "d.multicall2")


def test_rtorrent_missing_hash_status_is_not_treated_as_readable():
    client = FakeRTorrentClient()
    assert client._torrent_state(client._to_torrent_row([])) == TorrentState.UNKNOWN


@pytest.mark.asyncio
async def test_rtorrent_lookup_distinguishes_missing_torrent_from_query_failure(monkeypatch):
    client = FakeRTorrentClient()

    missing = await client.lookup_torrent_info("missing")
    monkeypatch.setattr(client, "_load_torrent_rows", AsyncMock(side_effect=ValueError("offline")))
    unavailable = await client.lookup_torrent_info("abc")

    assert missing.status == DownloadInfoLookupStatus.MISSING
    assert unavailable.status == DownloadInfoLookupStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_rtorrent_capability_degrades_unsupported_operations():
    client = FakeRTorrentClient()
    caps = client.capabilities()

    assert caps.can_apply_categories is False
    assert caps.can_apply_tags is False
    assert caps.can_delete_files is True
    assert caps.delete_files_requires_aethera is True
    assert caps.can_export_torrent is False
    assert caps.can_set_location is True
    assert caps.location_update_requires_aethera_move is True
    assert await client.delete_torrent("abc", delete_files=True) is True
    assert await client.export_torrent("abc") is None
    assert await client.set_torrent_location(["abc"], "/target") is True
    assert ("d.directory.set", ("ABC", "/target")) in client.calls
