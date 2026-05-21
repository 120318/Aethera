from pathlib import Path

from app.schemas.domain.media_types import MediaType
from app.schemas.exception.exceptions import InvalidRequestException, ResourceNotFoundException
from app.schemas.domain.resource_attributes import ResourceAttributes, NamingContext
from app.services.domain.library.naming_policy import combine_templates, format_name, migrate_template_tokens, split_legacy_template
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

router = APIRouter()


class PreviewRequest(BaseModel):
    template: str | None = None  # Internal note.
    dir_template: str | None = None
    file_template: str | None = None
    template_id: str | None = None  # Internal note.
    media_type: MediaType | None = None
    sample: NamingContext | None = None

    def _resolve_media_type(self) -> MediaType | None:
        candidates = (
            self.media_type,
            self.sample.media_type if self.sample else None,
            self.sample.attributes.content_type if self.sample else None,
        )
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                return MediaType(candidate)
            except ValueError:
                continue
        return None

    @model_validator(mode="after")
    def validate_tv_sample_requires_season_number(self) -> "PreviewRequest":
        if not self.sample:
            return self
        media_type = self._resolve_media_type()
        if media_type == MediaType.tv and self.sample.season_number is None:
            raise ValueError("tv naming preview sample must include season_number")
        return self

class TemplatePreviewResponse(BaseModel):
    dir_preview: str = ""
    file_preview: str = ""
    preview: str
    preview_with_extension: str | None = Field(default=None)
    disc_dir_preview: str = ""
    disc_file_preview: str = ""
    disc_preview: str = ""
    disc_preview_with_extension: str | None = Field(default=None)


def _default_preview_sample(media_type: MediaType | None) -> NamingContext:
    if media_type == MediaType.tv:
        return NamingContext(
            resource_title="Example Series", torrent_name="Example.Series.2021.S01E02.1080p.WEB-DL.mkv",
            season_number=1, media_type=MediaType.tv.value,
            attributes=ResourceAttributes(episodes=[2], resolution="1080p", video_codec="HEVC", groups=["GROUP"], content_type="tv", first_air_date="2021-02-15"),
        )
    return NamingContext(
        resource_title="Example Movie", torrent_name="Example.Movie.2021.1080p.WEB-DL.mkv", media_type=MediaType.movie.value,
        attributes=ResourceAttributes(resolution="1080p", video_codec="AVC", groups=["GROUP"], content_type="movie", release_date="2021-05-20"),
    )


@router.post("/config/preview", response_model=TemplatePreviewResponse)
def preview_template(payload: PreviewRequest):
    """Render a template preview using a small sample record or provided sample."""
    dir_template = ""
    file_template = ""

    if payload.dir_template is not None or payload.file_template is not None:
        dir_template = migrate_template_tokens(payload.dir_template or "")
        file_template = migrate_template_tokens(payload.file_template or "")
    elif payload.template:
        dir_template, file_template = split_legacy_template(migrate_template_tokens(payload.template))
    elif payload.template_id:
        template = next((t for t in settings_service.list_naming_templates() if t.id == payload.template_id), None)
        if template:
            dir_template = template.dir_template
            file_template = template.file_template
        else:
            raise ResourceNotFoundException("backendErrors.config.templateNotFound", params={"id": payload.template_id})
    elif payload.media_type:
        templates = settings_service.list_naming_templates()
        if payload.media_type == MediaType.movie:
            template_id = settings_service.get_default_movie_template_id()
            template = next((t for t in templates if t.id == template_id), None) if template_id else None
            if template:
                dir_template = template.dir_template
                file_template = template.file_template
        elif payload.media_type == MediaType.tv:
            template_id = settings_service.get_default_tv_template_id()
            template = next((t for t in templates if t.id == template_id), None) if template_id else None
            if template:
                dir_template = template.dir_template
                file_template = template.file_template

    if not (dir_template or file_template):
        raise InvalidRequestException("backendErrors.config.templatePreviewSourceRequired")

    sample = payload.sample or _default_preview_sample(payload.media_type)

    try:
        dir_preview = format_name(dir_template, sample) if dir_template else ""
        file_preview = format_name(file_template, sample) if file_template else ""
    except ValueError as exc:
        raise InvalidRequestException("backendErrors.config.templatePreviewFailed", params={"reason": str(exc)}) from exc
    rendered = combine_templates(dir_preview, file_preview)

    preview_with_ext = None
    sample_name = sample.torrent_name
    if sample_name and file_preview:
        ext = Path(sample_name).suffix
        if ext:
            preview_with_ext = combine_templates(dir_preview, f"{file_preview}{ext}")

    disc_sample = sample.model_copy(deep=True)
    disc_sample.attributes = disc_sample.attributes.model_copy(update={"resource_form": "BluRay Disc", "package_layout": "BDMV", "disc_number": 1, "disc_total": 2, "episodes": []})
    disc_sample.naming_category = "extra_episode"
    try:
        disc_dir_preview = format_name(dir_template, disc_sample) if dir_template else ""
        disc_file_preview = format_name(file_template, disc_sample) if file_template else ""
    except ValueError:
        disc_dir_preview = ""
        disc_file_preview = ""
    disc_preview = combine_templates(disc_dir_preview, disc_file_preview)
    disc_preview_with_ext = None
    if disc_file_preview:
        disc_preview_with_ext = combine_templates(disc_dir_preview, f"{disc_file_preview}.iso")

    return TemplatePreviewResponse(
        dir_preview=dir_preview,
        file_preview=file_preview,
        preview=rendered,
        preview_with_extension=preview_with_ext,
        disc_dir_preview=disc_dir_preview,
        disc_file_preview=disc_file_preview,
        disc_preview=disc_preview,
        disc_preview_with_extension=disc_preview_with_ext,
    )
