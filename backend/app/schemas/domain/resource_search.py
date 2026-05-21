from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.media_id import MediaID
from app.schemas.domain.media_types import MediaType


class MediaSearchQuery(BaseModel):
    media: MediaExecutionSnapshot
    indexers: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)
    use_cache: bool = True

    @property
    def media_id(self) -> MediaID:
        return self.media.media_id

    @property
    def imdbid(self) -> str | None:
        return self.media.imdb_id

    @property
    def douban_id(self) -> str | None:
        return self.media.douban_id

    @property
    def title(self) -> str:
        return self.media.title

    @property
    def year(self) -> int:
        return self.media.year

    @property
    def media_type(self) -> MediaType:
        return self.media.media_type

    @property
    def season_number(self) -> int | None:
        return self.media.season_number


class ResourceSearchResult(BaseModel):
    id: str
    title: str
    description: str = ""
    site: str
    site_name: str = ""
    indexer_id: str = ""
    indexer_name: str = ""
    indexer_type: str = ""
    category: str
    size: str
    seeders: int
    leechers: int
    publish_date: datetime
    torrent_url: str = ""
    download_url: str
    detail_url: str = ""
    result_id: str
    download_volume_factor: float | None = None
    upload_volume_factor: float | None = None
    matched_by_id: bool = True
    matched_unmatched_rule: bool = False
    source_imdbid: str | None = Field(default=None, exclude=True, repr=False)
    source_doubanid: str | None = Field(default=None, exclude=True, repr=False)


class Resource(BaseModel):
    """Combination model of a search result with parsed attributes."""
    model_config = ConfigDict(from_attributes=True)

    resources: ResourceSearchResult
    attrs: ResourceAttributes


class JackettSearchResult(BaseModel):
    """Raw search result from Jackett API"""
    model_config = ConfigDict(extra="allow")

    FirstSeen: datetime | None = None
    Tracker: str = "unknown"
    TrackerId: str | None = None
    TrackerType: str | None = None
    Category: list[int] = Field(default_factory=list)
    CategoryDesc: str = ""
    Blacklisted: bool = False
    Title: str = ""
    Guid: str = ""
    Link: str = ""
    Comments: str | None = None
    PublishDate: datetime = Field(default_factory=datetime.now)
    Size: int = 0
    Description: str | None = ""
    Details: str = ""
    Seeders: int = 0
    Peers: int = 0
    DownloadVolumeFactor: float | None = None
    UploadVolumeFactor: float | None = None
    MagnetUri: str | None = None
    InfoHash: str | None = None
    Files: int | None = None
    Grabs: int | None = None


class JackettSearchResponse(BaseModel):
    """Full response from Jackett API"""
    Results: list[JackettSearchResult] = Field(default_factory=list)
