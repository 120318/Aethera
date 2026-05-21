from app.clients.douban import DoubanClient
from app.clients.tmdb import TMDBClient
from app.schemas.config import DoubanConfig, TMDBConfig
from app.services.config.settings_service import settings_service


class MediaProviderClients:
    def get_douban_config(self) -> DoubanConfig:
        return settings_service.get_base_services_config().douban

    def get_tmdb_config(self) -> TMDBConfig:
        return settings_service.get_base_services_config().themoviedb

    def get_douban_client(self) -> DoubanClient | None:
        try:
            config = self.get_douban_config()
            return DoubanClient(config)
        except (RuntimeError, ValueError):
            return None

    def get_tmdb_client(self) -> TMDBClient:
        return TMDBClient(self.get_tmdb_config())
