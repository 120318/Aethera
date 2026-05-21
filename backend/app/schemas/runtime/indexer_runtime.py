from pydantic import BaseModel, Field

from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.integration.site_models import IndexerSiteSetting, SiteInfo, SiteSearchCapabilities


class IndexerSearchContext(BaseModel):
    indexer_id: str
    indexer_name: str = ""
    indexer_type: str = ""
    site: SiteInfo
    capabilities: SiteSearchCapabilities
    setting: IndexerSiteSetting
    cache_scope: str


class IndexerSiteSearchOutcome(BaseModel):
    indexer_id: str
    indexer_name: str = ""
    indexer_type: str = ""
    site: SiteInfo
    success: bool
    results: list[ResourceSearchResult] = Field(default_factory=list)
    error: str | None = None


class CachedIndexerSearchPayload(BaseModel):
    status: str = "ok"
    result_ids: list[str] = Field(default_factory=list)
    results: list[ResourceSearchResult] = Field(default_factory=list)
    error: str | None = None
    updated_at: float
    search_duration_seconds: float | None = None


class CachedIndexerResultPayload(BaseModel):
    result: ResourceSearchResult


class CachedIndexerSearchRecord(BaseModel):
    key: str
    status: str = "ok"
    result_ids: list[str] = Field(default_factory=list)
    results: list[ResourceSearchResult] = Field(default_factory=list)
    error: str | None = None
    updated_at: float
