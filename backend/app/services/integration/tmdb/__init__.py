from app.clients.factory import ClientFactory, ClientType
from app.schemas.config import TMDBConfig
from app.services.integration.tmdb.schedule import TMDBScheduleGateway, tmdb_schedule_gateway
from app.services.integration.tmdb.images import to_tmdb_image_url


async def test_connection_for_config(config: TMDBConfig) -> bool:
    client = ClientFactory.create_client_with_config(ClientType.TMDB, config)
    return await client.test_connection()


__all__ = ["TMDBScheduleGateway", "test_connection_for_config", "tmdb_schedule_gateway", "to_tmdb_image_url"]
