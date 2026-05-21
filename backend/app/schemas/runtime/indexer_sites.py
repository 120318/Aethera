from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType


class IndexerSiteSettingsPayload(BaseModel):
    enabled: bool = True
    disable_title: bool = False
    disable_imdb: bool = False
    disable_douban: bool = False
    media_types: list[MediaType] | None = None


class IndexerSiteCapabilitiesPayload(BaseModel):
    supports_title: bool = False
    supports_imdb: bool = False
    supports_douban: bool = False
    supports_movie: bool = True
    supports_tv: bool = True


class IndexerSiteEffectivePayload(BaseModel):
    enabled: bool = False
    use_title: bool = False
    use_imdb: bool = False
    use_douban: bool = False
    supports_movie: bool = True
    supports_tv: bool = True
    media_types_source: str = "auto"


class IndexerSiteStatusItem(BaseModel):
    site_id: str
    site_name: str = ""
    description: str = ""
    language: str = ""
    type: str = ""
    is_live: bool = False
    settings: IndexerSiteSettingsPayload = Field(default_factory=IndexerSiteSettingsPayload)
    capabilities: IndexerSiteCapabilitiesPayload = Field(default_factory=IndexerSiteCapabilitiesPayload)
    effective: IndexerSiteEffectivePayload = Field(default_factory=IndexerSiteEffectivePayload)


class IndexerSitesGroup(BaseModel):
    indexer_id: str
    indexer_name: str = ""
    sites: list[IndexerSiteStatusItem] = Field(default_factory=list)
    error: str | None = None


class IndexerSitesResponse(BaseModel):
    indexers: list[IndexerSitesGroup] = Field(default_factory=list)
