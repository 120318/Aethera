from app.api.v1.config.preview import PreviewRequest, preview_template
from app.schemas.domain.media_types import MediaType


def test_movie_template_preview_uses_canonical_codec_value():
    response = preview_template(
        PreviewRequest(
            media_type=MediaType.movie,
            dir_template="{title} ({year})",
            file_template="{title} - {resolution} - {videoCodec}",
        )
    )

    assert response.preview
    assert "unknown_" not in response.preview
