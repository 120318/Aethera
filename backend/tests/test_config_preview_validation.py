from pydantic import ValidationError

from app.api.v1.config.preview import PreviewRequest
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import NamingContext, ResourceAttributes


def test_tv_preview_sample_requires_season_number_when_media_type_is_enum():
    try:
        PreviewRequest(
            media_type=MediaType.tv,
            dir_template="{title}",
            sample=NamingContext(
                resource_title="Example Series",
                media_type=MediaType.tv.value,
                attributes=ResourceAttributes(content_type=MediaType.tv.value),
            ),
        )
    except ValidationError as exc:
        assert "tv naming preview sample must include season_number" in str(exc)
    else:
        raise AssertionError("expected TV preview sample validation to require season_number")
