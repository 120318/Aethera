from typing import cast

from app.clients.factory import ClientFactory, ClientType
from app.schemas.config import DownloaderProviderConfig
from app.services.integration.download.client import DownloadClient


class DownloadGateway:
    async def test_connection_for_config(self, downloader: DownloaderProviderConfig) -> bool:
        client = cast(DownloadClient, ClientFactory.create_client_with_config(ClientType(downloader.type), downloader))
        try:
            return await client.test_connection()
        finally:
            await client.close()


download_gateway = DownloadGateway()
