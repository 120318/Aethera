from pydantic import BaseModel, Field, RootModel
from datetime import datetime

class TorznabAttr(BaseModel):
    name: str
    value: str

class TorznabEnclosure(BaseModel):
    url: str
    length: int | None = None
    type: str | None = None

class TorznabItem(BaseModel):
    title: str
    guid: str | None = None
    link: str | None = None
    comments: str | None = None
    pubDate: str | None = None
    description: str | None = None
    enclosure: TorznabEnclosure | None = None
    jackettindexer: str | None = None
    # Dictionary to hold torznab:attr entries by name
    attributes: dict[str, str] = Field(default_factory=dict)

    @property
    def size(self) -> int:
        if "size" in self.attributes:
            return int(float(self.attributes["size"]))
        if self.enclosure and self.enclosure.length:
            return self.enclosure.length
        return 0

    @property
    def seeders(self) -> int:
        return int(self.attributes.get("seeders", 0))

    @property
    def peers(self) -> int:
        return int(self.attributes.get("peers", self.attributes.get("leechers", 0)))

    @property
    def download_volume_factor(self) -> float | None:
        value = self.attributes.get("downloadvolumefactor")
        if value is None:
            return None
        return float(value)

    @property
    def upload_volume_factor(self) -> float | None:
        value = self.attributes.get("uploadvolumefactor")
        if value is None:
            return None
        return float(value)
