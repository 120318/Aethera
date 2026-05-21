from app.clients.factory import ClientFactory, ClientType
from app.schemas.config import DoubanConfig


async def test_connection_for_config(config: DoubanConfig) -> bool:
    client = ClientFactory.create_client_with_config(ClientType.DOUBAN, config)
    return await client.test_connection()


__all__ = ["test_connection_for_config"]
