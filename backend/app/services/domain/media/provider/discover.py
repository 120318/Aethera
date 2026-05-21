from app.schemas.media_id import MediaID, Provider
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.search_models import MediaSearchResult
from app.services.domain.media.provider.clients import MediaProviderClients


class MediaProviderDiscover:
    def __init__(self, clients: MediaProviderClients) -> None:
        self.clients = clients

    def supports_discover_key(self, key: str) -> bool:
        client = self.clients.get_douban_client()
        return bool(client and client.supports_discover_key(key))

    def supports_tmdb_discover_key(self, key: str) -> bool:
        client = self.clients.get_tmdb_client()
        return bool(client and client.supports_discover_key(key))

    def discover_available(self) -> bool:
        client = self.clients.get_douban_client()
        return bool(client and client.api_key and client.api_secret)

    def tmdb_discover_available(self) -> bool:
        client = self.clients.get_tmdb_client()
        return bool(client and client.api_key)

    async def discover_items(self, key: str, start: int = 0, count: int = 20):
        client = self.clients.get_douban_client()
        if not client:
            return []
        return await client.subject_collection_items(key, start=start, count=count)

    async def tmdb_discover_items(self, key: str, start: int = 0, count: int = 20):
        client = self.clients.get_tmdb_client()
        if not client.api_key:
            return []
        return await client.discover_items(key, start=start, count=count)


def canonical_tmdb_media_id(media_type: MediaType, tmdb_id: int) -> MediaID:
    return MediaID(provider=Provider.tmdb, media_type=media_type, id=str(tmdb_id))
