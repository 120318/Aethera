from __future__ import annotations

from enum import Enum

from app.schemas.domain.media_types import MediaType
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_serializer, model_validator


class Provider(str, Enum):
    douban = "douban"
    tmdb = "tmdb"

# 1. text：text -> text

class MediaIDModel(BaseModel):
    media_id: MediaID
    @field_serializer('media_id', when_used='always')
    def serialize_media_id(self, v: MediaID):
        return str(v) # Internal note.

class MediaID(BaseModel):
    """Structured representation of a media identifier.

    Canonical serialized forms:
      - movie: `provider:movie:id`
      - tv: `provider:tv:id`
    """

    model_config = ConfigDict(frozen=True)

    provider: Provider
    media_type: MediaType
    id: str

    @model_validator(mode='before')
    @classmethod
    def parse_from_string(cls, value):
        if type(value) is str:
            # Convert canonical string into structured fields for validation.
            # Note: we cannot return a MediaID instance here because Pydantic's
            # "before" validator expects raw data (dict-like), not a model.
            parsed = cls.parse(value)
            return {
                "provider": parsed.provider,
                "media_type": parsed.media_type,
                "id": parsed.id,
            }
        return value

    @model_serializer(mode="plain")
    def serialize(self) -> str:
        return self.to_string()
    
    @classmethod
    def parse(cls, value: str) -> "MediaID":
        if type(value) is not str:
            raise TypeError("MediaID.parse expects a str, got: %s, value: %s" % (type(value), value))
        parts = value.split(":")
        if len(parts) < 3:
            raise ValueError("media_id must be in form provider:media_type:id")
        provider_raw = parts[0]
        try:
            provider = Provider(provider_raw)
        except ValueError:
            raise ValueError(f"unknown provider: {provider_raw}")
        media_type = MediaType(parts[1])
        raw_id = parts[2]
        if len(parts) != 3:
            raise ValueError("media_id must be in form provider:media_type:id")
        return cls(provider=provider, media_type=media_type, id=raw_id)

    @field_validator("media_type", "id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("media_type and id must be non-empty strings")
        return v

    def to_string(self) -> str:
        return f"{self.provider.value}:{self.media_type.value}:{self.id}"

    def __str__(self) -> str:
        return self.to_string()
