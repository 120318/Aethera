from pydantic import BaseModel, ConfigDict, Field


class TMDBSearchItem(BaseModel):
    id: int | None = None
    title: str | None = None
    name: str | None = None
    original_title: str | None = None
    original_name: str | None = None
    release_date: str | None = None
    first_air_date: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    genre_ids: list[int] = Field(default_factory=list)
    original_language: str | None = None
    popularity: float | None = None
    vote_average: float | None = None
    vote_count: int | None = None

    model_config = ConfigDict(extra="allow")


class TMDBExternalIDs(BaseModel):
    imdb_id: str | None = None
    facebook_id: str | None = None
    instagram_id: str | None = None
    twitter_id: str | None = None
    tvdb_id: int | None = None

    model_config = ConfigDict(extra="allow")


class TMDBImage(BaseModel):
    file_path: str
    iso_639_1: str | None = None
    aspect_ratio: float | None = None
    height: int | None = None
    width: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None


class TMDBImages(BaseModel):
    backdrops: list[TMDBImage] = Field(default_factory=list)
    posters: list[TMDBImage] = Field(default_factory=list)
    logos: list[TMDBImage] = Field(default_factory=list)


class TMDBCast(BaseModel):
    id: int
    name: str
    character: str | None = None
    profile_path: str | None = None
    order: int | None = None


class TMDBCrew(BaseModel):
    id: int
    name: str
    job: str | None = None
    department: str | None = None
    profile_path: str | None = None


class TMDBCredits(BaseModel):
    cast: list[TMDBCast] = Field(default_factory=list)
    crew: list[TMDBCrew] = Field(default_factory=list)


class TMDBAggregateRole(BaseModel):
    character: str | None = None
    episode_count: int | None = None

    model_config = ConfigDict(extra="allow")


class TMDBAggregateCast(BaseModel):
    id: int
    name: str
    profile_path: str | None = None
    order: int | None = None
    roles: list[TMDBAggregateRole] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBAggregateCrew(BaseModel):
    id: int | None = None
    name: str | None = None
    department: str | None = None
    job: str | None = None
    profile_path: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBAggregateCredits(BaseModel):
    cast: list[TMDBAggregateCast] = Field(default_factory=list)
    crew: list[TMDBAggregateCrew] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBGenre(BaseModel):
    id: int | None = None
    name: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBCreator(BaseModel):
    id: int | None = None
    name: str | None = None
    profile_path: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBProductionCompany(BaseModel):
    id: int | None = None
    name: str | None = None
    logo_path: str | None = None
    origin_country: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBNetwork(BaseModel):
    id: int | None = None
    name: str | None = None
    logo_path: str | None = None
    origin_country: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBWatchProvider(BaseModel):
    provider_id: int | None = None
    provider_name: str | None = None
    logo_path: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBRegionWatchProviders(BaseModel):
    link: str | None = None
    flatrate: list[TMDBWatchProvider] = Field(default_factory=list)
    ads: list[TMDBWatchProvider] = Field(default_factory=list)
    free: list[TMDBWatchProvider] = Field(default_factory=list)
    buy: list[TMDBWatchProvider] = Field(default_factory=list)
    rent: list[TMDBWatchProvider] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBSeason(BaseModel):
    id: int | None = None
    season_number: int | None = None
    air_date: str | None = None
    name: str | None = None
    overview: str | None = None
    episode_count: int | None = None
    poster_path: str | None = None

    model_config = ConfigDict(extra="allow")


class TMDBEpisode(BaseModel):
    id: int | None = None
    name: str | None = None
    overview: str | None = None
    air_date: str | None = None
    episode_number: int | None = None
    season_number: int | None = None
    still_path: str | None = None
    runtime: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    crew: list[TMDBCrew] = Field(default_factory=list)
    guest_stars: list[TMDBCast] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBSeasonDetails(BaseModel):
    id: int | None = None
    air_date: str | None = None
    name: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    season_number: int | None = None
    episodes: list[TMDBEpisode] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBDetails(BaseModel):
    id: int | None = None
    title: str | None = None
    name: str | None = None
    original_title: str | None = None
    original_name: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    status: str | None = None
    original_language: str | None = None
    runtime: int | None = None
    episode_run_time: list[int] = Field(default_factory=list)
    number_of_episodes: int | None = None
    production_companies: list[TMDBProductionCompany] = Field(default_factory=list)
    networks: list[TMDBNetwork] = Field(default_factory=list)
    created_by: list[TMDBCreator] = Field(default_factory=list)
    genres: list[TMDBGenre] = Field(default_factory=list)
    seasons: list[TMDBSeason] = Field(default_factory=list)
    seasons_count: int | None = None
    release_date: str | None = None
    first_air_date: str | None = None
    next_episode_to_air: TMDBEpisode | None = None
    external_ids: TMDBExternalIDs | None = None
    images: TMDBImages | None = None
    credits: TMDBCredits | None = None
    aggregate_credits: TMDBAggregateCredits | None = None

    model_config = ConfigDict(extra="allow")


class TMDBSearchResponse(BaseModel):
    page: int = 0
    results: list[TMDBSearchItem] = Field(default_factory=list)
    total_pages: int = 0
    total_results: int = 0


class TMDBWatchProvidersResponse(BaseModel):
    id: int = 0
    results: dict[str, TMDBRegionWatchProviders] = Field(default_factory=dict)


class TMDBReleaseDateItem(BaseModel):
    certification: str | None = None
    descriptors: list[str] = Field(default_factory=list)
    iso_639_1: str | None = None
    note: str | None = None
    release_date: str | None = None
    type: int | None = None

    model_config = ConfigDict(extra="allow")


class TMDBReleaseDateRegion(BaseModel):
    iso_3166_1: str | None = None
    release_dates: list[TMDBReleaseDateItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TMDBReleaseDatesResponse(BaseModel):
    id: int = 0
    results: list[TMDBReleaseDateRegion] = Field(default_factory=list)
