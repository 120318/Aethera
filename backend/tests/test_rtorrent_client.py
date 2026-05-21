from datetime import datetime

import pytest

from app.clients.rtorrent import RTorrentClient
from app.schemas.config import RTorrentConfig
from app.schemas.domain.torrent_status import TorrentState


class FakeRTorrentClient(RTorrentClient):
    def __init__(self):
        super().__init__(RTorrentConfig(id="rt", name="rt", url="http://rtorrent/RPC2"))
        self.calls = []

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
                    0,
                    1,
                    1,
                    int(datetime(2024, 1, 1).timestamp()),
                    75,
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
        ]
    )

    assert client._torrent_state(row) == TorrentState.PAUSED


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
