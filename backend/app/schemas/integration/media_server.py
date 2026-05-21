from pydantic import BaseModel, ConfigDict, Field


class JellyfinLibrary(BaseModel):
    """Jellyfin media library model"""
    model_config = ConfigDict(extra="allow")

    Name: str = ""
    Id: str = ""
    ItemId: str | None = None
    Path: str | None = None
    Locations: list[str] = Field(default_factory=list)
    Paths: list[str] = Field(default_factory=list)
    CollectionType: str | None = None
