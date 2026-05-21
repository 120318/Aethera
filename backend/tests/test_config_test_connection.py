import pytest

from app.api.v1.config import test_connection
from app.api.v1.config.test_connection import (
    TestConnectionConfig as ConnectionConfigPayload,
    TestServiceConnectionRequest as ServiceConnectionRequestPayload,
)


@pytest.mark.asyncio
async def test_test_connection_uses_request_service_type_for_downloader(monkeypatch):
    seen_types = []

    async def fake_test_connection_for_config(config):
        seen_types.append(config.type)
        return True

    monkeypatch.setattr(
        test_connection.download_gateway,
        "test_connection_for_config",
        fake_test_connection_for_config,
    )

    response = await test_connection.test_service_connection(
        ServiceConnectionRequestPayload(
            type="qbittorrent",
            config=ConnectionConfigPayload(
                type="",
                url="http://qbittorrent.local",
                username="user",
                password="pass",
            ),
        )
    )

    assert response.ok is True
    assert response.client_type == "qbittorrent"
    assert seen_types == ["qbittorrent"]


@pytest.mark.asyncio
async def test_test_connection_accepts_rtorrent_downloader(monkeypatch):
    seen_types = []

    async def fake_test_connection_for_config(config):
        seen_types.append(config.type)
        return True

    monkeypatch.setattr(
        test_connection.download_gateway,
        "test_connection_for_config",
        fake_test_connection_for_config,
    )

    response = await test_connection.test_service_connection(
        ServiceConnectionRequestPayload(
            type="rtorrent",
            config=ConnectionConfigPayload(
                type="",
                url="http://rtorrent.local/RPC2",
                username="user",
                password="pass",
            ),
        )
    )

    assert response.ok is True
    assert response.client_type == "rtorrent"
    assert seen_types == ["rtorrent"]
