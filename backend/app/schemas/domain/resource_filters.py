from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.domain.quality_values import (
    AudioChannelsValue,
    AudioCodecValue,
    ColorDepthValue,
    HdrTypeValue,
    ResourceFormValue,
    ResourceKindValue,
    ResolutionValue,
    SourceValue,
    VideoCodecValue,
)


class UpgradePolicy(BaseModel):
    enabled: bool = Field(default=False, description="Field description")
    strategy: Literal["consistent_allow_temp", "consistent_skip_low"] = Field(
        default="consistent_allow_temp",
        description="Field description",
    )
    min_upgrade_score_delta: int = Field(default=0, description="Field description")
    lock_mode: Literal["off", "first_download", "best_existing"] = Field(
        default="best_existing",
        description="Field description",
    )


class ResourceFilters(BaseModel):
    resource_kind: list[ResourceKindValue] = Field(default_factory=lambda: [ResourceKindValue.VIDEO_FILE], description="Field description")
    resolution: list[ResolutionValue] | None = Field(None, description="Field description")
    source: list[SourceValue] | None = Field(None, description="Field description")
    resource_form: list[ResourceFormValue] | None = Field(None, description="Field description")
    codec: list[VideoCodecValue] | None = Field(None, description="Field description")
    hdr_type: list[HdrTypeValue] | None = Field(None, description="HDR text")
    audio_codec: list[AudioCodecValue] | None = Field(None, description="Field description")
    audio_channels: list[AudioChannelsValue] | None = Field(None, description="Field description")
    color_depth: list[ColorDepthValue] | None = Field(None, description="Field description")
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    tags: list[str] | None = Field(None, description="Field description")
    upgrade_policy: UpgradePolicy | None = Field(None, description="Field description")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_tag_field(cls, value):
        if type(value) is not dict:
            return value
        payload = dict(value)
        if "tags" not in payload and "custom_tags" in payload:
            payload["tags"] = payload["custom_tags"]
        payload.pop("custom_tags", None)
        return payload

    @field_validator("resource_kind", mode="before")
    @classmethod
    def default_resource_kind(cls, value):
        if value is None or value == []:
            return [ResourceKindValue.VIDEO_FILE]
        return value

    @field_validator("hdr_type", mode="before")
    @classmethod
    def normalize_hdr_type(cls, value):
        if value is None:
            return value
        normalized = [
            HdrTypeValue.HDR10 if item == HdrTypeValue.HDR or item == HdrTypeValue.HDR.value else item
            for item in value
        ]
        deduped = []
        seen = set()
        for item in normalized:
            key = str(item)
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
        return deduped

    @model_validator(mode="after")
    def normalize_resource_form_scope(self) -> "ResourceFilters":
        if not self.resource_form:
            return self
        allowed_forms: set[ResourceFormValue] = set()
        if ResourceKindValue.VIDEO_FILE in self.resource_kind:
            allowed_forms.add(ResourceFormValue.VIDEO_FILE)
        if ResourceKindValue.ORIGINAL_DISC in self.resource_kind:
            allowed_forms.update({ResourceFormValue.BLURAY_DISC, ResourceFormValue.DVD_DISC})
        self.resource_form = [value for value in self.resource_form if value in allowed_forms]
        return self


class ResourceUnmatchedRule(BaseModel):
    sites: list[str] | None = None
    search_title: str | None = None
    pattern: str = ""

    @model_validator(mode="after")
    def normalize_text_fields(self) -> "ResourceUnmatchedRule":
        self.search_title = self.search_title.strip() if self.search_title and self.search_title.strip() else None
        self.pattern = self.pattern.strip() if self.pattern else ""
        return self
