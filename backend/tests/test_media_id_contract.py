import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID, Provider


class MediaIDEnvelope(BaseModel):
    media_id: MediaID


def test_media_id_parses_and_serializes_canonical_string():
    media_id = MediaID.parse("tmdb:movie:123")

    assert media_id.provider == Provider.tmdb
    assert media_id.media_type == MediaType.movie
    assert media_id.id == "123"
    assert str(media_id) == "tmdb:movie:123"


def test_media_id_pydantic_model_accepts_string_and_dumps_string():
    envelope = MediaIDEnvelope(media_id="douban:tv:456")

    assert envelope.media_id == MediaID.parse("douban:tv:456")
    assert envelope.model_dump(mode="json") == {"media_id": "douban:tv:456"}


@pytest.mark.parametrize(
    "raw",
    [
        "tmdb:movie",
        "tmdb:movie:123:season:1",
        "unknown:movie:123",
        "tmdb:book:123",
    ],
)
def test_media_id_rejects_invalid_canonical_strings(raw):
    with pytest.raises(ValueError):
        MediaID.parse(raw)


def test_media_id_rejects_empty_fields_in_model_validation():
    with pytest.raises(ValidationError):
        MediaID(provider=Provider.tmdb, media_type=MediaType.movie, id="")
