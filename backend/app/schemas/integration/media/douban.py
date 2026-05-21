from pydantic import BaseModel, ConfigDict, Field


class DoubanRating(BaseModel):
    count: int = 0
    max: int = 10
    star_count: float = 0.0
    value: float = 0.0


class DoubanPic(BaseModel):
    large: str | None = None
    normal: str | None = None


class DoubanCollectionCover(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str | None = None
    width: int | None = None
    height: int | None = None
    shape: str | None = None


class DoubanAvatar(BaseModel):
    large: str | None = None
    normal: str | None = None


class DoubanCelebrity(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    roles: list[str] = Field(default_factory=list)
    title: str | None = None
    url: str | None = None
    character: str | None = None
    uri: str | None = None
    avatar: DoubanAvatar | None = None
    sharing_url: str | None = None
    type: str | None = None
    id: str | None = None
    latin_name: str | None = None


class DoubanVendorPayment(BaseModel):
    model_config = ConfigDict(extra="allow")


class DoubanVendor(BaseModel):
    model_config = ConfigDict(extra="allow")

    app_uri: str | None = None
    grey_icon: str | None = None
    title: str | None = None
    promote_desc: str | None = None
    app_bundle_id: str | None = None
    click_tracking: str | None = None
    labels: list[str] = Field(default_factory=list)
    uri: str | None = None
    subject_id: str | None = None
    episodes_info: str | None = None
    url: str | None = None
    book_type_cn: str | None = None
    book_type: str | None = None
    payments: list[DoubanVendorPayment] = Field(default_factory=list)
    payment_desc: str | None = None
    pre_release_desc: str | None = None
    id: str | None = None
    is_ad: bool | None = None
    impression_tracking: str | None = None
    icon: str | None = None


class DoubanSearchTarget(BaseModel):
    model_config = ConfigDict(extra="allow")

    rating: DoubanRating | None = None
    controversy_reason: str | None = None
    title: str | None = None
    abstract: str | None = None
    has_linewatch: bool | None = None
    uri: str | None = None
    cover_url: str | None = None
    year: int | None = None
    card_subtitle: str | None = None
    id: str
    null_rating_reason: str | None = None


class DoubanSearchItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    layout: str | None = None
    type_name: str | None = None
    target_id: str | None = None
    target: DoubanSearchTarget
    target_type: str | None = None


class DoubanSearchSubjects(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[DoubanSearchItem] = Field(default_factory=list)


class DoubanCollectionItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: DoubanSearchTarget | None = None
    target: DoubanSearchTarget | None = None
    rating: DoubanRating | None = None
    title: str | None = None
    year: int | None = None
    id: str | None = None
    card_subtitle: str | None = None
    type: str | None = None
    pic: DoubanPic | None = None
    cover_url: str | None = None
    cover: DoubanCollectionCover | None = None


class DoubanRawCollectionItemsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[DoubanCollectionItem] = Field(default_factory=list)
    subject_collection_items: list[DoubanCollectionItem] = Field(default_factory=list)


class DoubanCollectionItemsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[DoubanCollectionItem] = Field(default_factory=list)


class DoubanIMDBLookupResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class DoubanSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    count: int | None = None
    start: int | None = None
    banned: str | None = None
    total: int | None = None
    smart_box: list[DoubanSearchItem] = Field(default_factory=list)
    items: list[DoubanSearchItem] = Field(default_factory=list)
    subjects: DoubanSearchSubjects | None = None


class DoubanDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    rating: DoubanRating | None = None
    lineticket_url: str | None = None
    controversy_reason: str | None = None
    pubdate: list[str] = Field(default_factory=list)
    last_episode_number: int | None = None
    pic: DoubanPic | None = None
    vendor_count: int | None = None
    body_bg_color: str | None = None
    is_tv: bool | None = None
    card_subtitle: str | None = None
    intro: str | None = None
    ticket_price_info: str | None = None
    year: int
    id: str | None = None
    gallery_topic_count: int | None = None
    languages: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    review_count: int | None = None
    title: str | None = None
    has_linewatch: bool | None = None
    forum_topic_count: int | None = None
    is_released: bool | None = None
    vendors: list[DoubanVendor] = Field(default_factory=list)
    actors: list[DoubanCelebrity] = Field(default_factory=list)
    directors: list[DoubanCelebrity] = Field(default_factory=list)
    durations: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    original_title: str | None = None
    episodes_count: int | None = None


class DoubanCelebritiesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    directors: list[DoubanCelebrity] = Field(default_factory=list)
    total: int | None = None
    actors: list[DoubanCelebrity] = Field(default_factory=list)


__all__ = [
    "DoubanRating",
    "DoubanPic",
    "DoubanCollectionCover",
    "DoubanAvatar",
    "DoubanCelebrity",
    "DoubanVendor",
    "DoubanSearchTarget",
    "DoubanSearchItem",
    "DoubanSearchSubjects",
    "DoubanCollectionItem",
    "DoubanRawCollectionItemsResponse",
    "DoubanCollectionItemsResponse",
    "DoubanIMDBLookupResponse",
    "DoubanSearchResult",
    "DoubanDetail",
    "DoubanCelebritiesResponse",
]
