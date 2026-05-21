from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import (
    DoubanConfig,
    JackettConfig,
    JellyfinConfig,
    PathMapping,
    ProwlarrConfig,
    RTorrentConfig,
    TMDBConfig,
    QBittorrentConfig,
)
from app.schemas.exception import ServiceTypeException, TestConnectionException
from app.services.integration import douban as douban_integration
from app.services.integration import tmdb as tmdb_integration
from app.services.integration.download.gateway import download_gateway
from app.services.integration.indexer import indexer_gateway
from app.services.integration.media_server import media_server_gateway

router = APIRouter()

SERVICE_TYPE_QBITTORRENT = "qbittorrent"
SERVICE_TYPE_RTORRENT = "rtorrent"
SERVICE_TYPE_JACKETT = "jackett"
SERVICE_TYPE_PROWLARR = "prowlarr"
SERVICE_TYPE_JELLYFIN = "jellyfin"
SERVICE_TYPE_TMDB = "themoviedb"
SERVICE_TYPE_DOUBAN = "douban"
SUPPORTED_SERVICE_TYPES = [
    SERVICE_TYPE_QBITTORRENT,
    SERVICE_TYPE_RTORRENT,
    SERVICE_TYPE_JACKETT,
    SERVICE_TYPE_PROWLARR,
    SERVICE_TYPE_JELLYFIN,
    SERVICE_TYPE_TMDB,
    SERVICE_TYPE_DOUBAN,
]


class TestConnectionConfig(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    enabled: bool = True
    url: str | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    path_mappings: list[PathMapping] = []


class TestServiceConnectionRequest(BaseModel):
    type: str
    config: TestConnectionConfig


class TestConnectionResponse(BaseModel):
    ok: bool
    client_type: str | None = None


@router.post("/config/test-connection", response_model=TestConnectionResponse)
async def test_service_connection(payload: TestServiceConnectionRequest):
    """Test connection to a service using provided credentials.
    
    Returns 200 on successful connection, 400/500 on failure with details.
    """
    service_type = payload.type
    config_data = payload.config.model_dump(mode="python")
    config_data["type"] = service_type
    
    if service_type == SERVICE_TYPE_QBITTORRENT:
        config = QBittorrentConfig.model_validate(config_data)
        success = await download_gateway.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_RTORRENT:
        config = RTorrentConfig.model_validate(config_data)
        success = await download_gateway.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_JACKETT:
        config = JackettConfig.model_validate(config_data)
        success = await indexer_gateway.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_PROWLARR:
        config = ProwlarrConfig.model_validate(config_data)
        success = await indexer_gateway.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_JELLYFIN:
        config = JellyfinConfig.model_validate(config_data)
        success = await media_server_gateway.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_TMDB:
        config = TMDBConfig.model_validate(config_data)
        success = await tmdb_integration.test_connection_for_config(config)
    elif service_type == SERVICE_TYPE_DOUBAN:
        config = DoubanConfig.model_validate(config_data)
        success = await douban_integration.test_connection_for_config(config)
    else:
        raise ServiceTypeException(service_type=service_type, supported_types=SUPPORTED_SERVICE_TYPES)

    if success:
        return TestConnectionResponse(ok=True, client_type=service_type)
    raise TestConnectionException(service_name=service_type)
            
