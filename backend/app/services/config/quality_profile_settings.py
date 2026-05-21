from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.db.sql.models import MediaSubscriptionSettingsORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.quality_ranking import (
    QUALITY_DIMENSION_AUDIO_CHANNELS,
    QUALITY_DIMENSION_AUDIO_CODEC,
    QUALITY_DIMENSION_HDR_TYPE,
    QUALITY_DIMENSION_RESOURCE_FORM,
    QUALITY_DIMENSION_RESOLUTION,
    QUALITY_DIMENSION_SOURCE,
    QUALITY_DIMENSION_VIDEO_CODEC,
    QualityRankingConfig,
)
from app.schemas.domain.quality_values import (
    AudioChannelsValue,
    AudioCodecValue,
    HdrTypeValue,
    ResourceFormValue,
    ResolutionValue,
    SourceValue,
    VideoCodecValue,
)
from app.schemas.exception import ConfigurationException

class _Missing:
    pass


MISSING = _Missing()
DEFAULT_QUALITY_PROFILE_ID = "builtin-quality-profile-default"


class QualityProfileSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self) -> list[QualityProfile]:
        return self._repo.quality_profiles.list()

    def replace_all(self, profiles: list[QualityProfile]) -> None:
        self._repo.quality_profiles.replace(profiles)

    def find(self, profile_id: str) -> QualityProfile | None:
        return next((profile for profile in self.list() if profile.id == profile_id), None)

    def get_default(self) -> QualityProfile | None:
        profiles = self.list()
        return next((item for item in profiles if item.active_default), None) or (profiles[0] if profiles else None)

    def get_default_id(self) -> str | None:
        profile = self.get_default()
        return profile.id if profile else None

    def create(
        self,
        name: str,
        ranking,
        min_score: int | None = None,
        tag_scores: dict[str, int] | None = None,
        active_default: bool = False,
    ) -> QualityProfile:
        profiles = self.list()
        if active_default:
            profiles = [item.model_copy(update={"active_default": False}) for item in profiles]
        profile = QualityProfile(
            id=str(uuid.uuid4()),
            name=name,
            is_default=False,
            active_default=active_default,
            ranking=ranking,
            min_score=min_score,
            tag_scores=tag_scores or {},
        )
        profiles.append(profile)
        self.replace_all(profiles)
        return profile

    def update(
        self,
        profile_id: str,
        *,
        name=MISSING,
        ranking=MISSING,
        min_score=MISSING,
        tag_scores=MISSING,
        active_default=MISSING,
    ) -> QualityProfile | None:
        profiles = self.list()
        if active_default is True:
            profiles = [
                item.model_copy(update={"active_default": False}) if item.id != profile_id else item
                for item in profiles
            ]
        current_default_id = next((item.id for item in profiles if item.active_default), None)
        for index, profile in enumerate(profiles):
            if profile.id != profile_id:
                continue
            profiles[index] = profile.model_copy(
                update={
                    "name": profile.name if name is MISSING else name,
                    "ranking": profile.ranking if ranking is MISSING else ranking,
                    "min_score": profile.min_score if min_score is MISSING else min_score,
                    "tag_scores": profile.tag_scores if tag_scores is MISSING else (tag_scores or {}),
                    "active_default": profile.active_default if active_default is MISSING else bool(active_default),
                }
            )
            if not any(item.active_default for item in profiles) and profiles:
                fallback_index = next(
                    (item_index for item_index, item in enumerate(profiles) if item.id == (current_default_id or profile_id)),
                    0,
                )
                profiles[fallback_index] = profiles[fallback_index].model_copy(update={"active_default": True})
            self.replace_all(profiles)
            return profiles[index]
        return None

    def delete(self, profile_id: str, referenced_filter_names: list[str]) -> bool:
        profiles = self.list()
        removed = next((item for item in profiles if item.id == profile_id), None)
        if removed and referenced_filter_names:
            raise ConfigurationException(
                "backendErrors.config.qualityProfileReferencedByFilters",
                params={"names": ", ".join(referenced_filter_names)},
            )
        if removed:
            with SessionLocal() as session:
                media_config_refs = session.scalar(
                    select(func.count())
                    .select_from(MediaSubscriptionSettingsORM)
                    .where(MediaSubscriptionSettingsORM.quality_profile_id == profile_id)
                ) or 0
            if media_config_refs > 0:
                raise ConfigurationException(
                    "backendErrors.config.qualityProfileReferencedByMediaConfigs",
                    params={"count": str(media_config_refs)},
                )
        next_profiles = [item for item in profiles if item.id != profile_id]
        if len(next_profiles) == len(profiles):
            return False
        if removed and removed.active_default and next_profiles:
            next_profiles[0] = next_profiles[0].model_copy(update={"active_default": True})
        self.replace_all(next_profiles)
        return True

    def ensure_defaults(self) -> None:
        if self.list():
            return
        self.replace_all(
            [
                QualityProfile(
                    id=DEFAULT_QUALITY_PROFILE_ID,
                    name="Default quality profile",
                    is_default=False,
                    active_default=True,
                    ranking=self._build_seed_ranking(),
                    min_score=None,
                    tag_scores={},
                )
            ]
        )

    def _build_seed_ranking(self) -> QualityRankingConfig:
        return QualityRankingConfig(
            dimension_order=[
                QUALITY_DIMENSION_RESOLUTION,
                QUALITY_DIMENSION_HDR_TYPE,
                QUALITY_DIMENSION_SOURCE,
                QUALITY_DIMENSION_RESOURCE_FORM,
                QUALITY_DIMENSION_AUDIO_CODEC,
                QUALITY_DIMENSION_VIDEO_CODEC,
                QUALITY_DIMENSION_AUDIO_CHANNELS,
            ],
            resolution=[
                ResolutionValue.UHD_2160P,
                ResolutionValue.QHD_1440P,
                ResolutionValue.FHD_1080P,
                ResolutionValue.HD_720P,
                ResolutionValue.SD_576P,
                ResolutionValue.SD_480P,
            ],
            source=[
                SourceValue.REMUX,
                SourceValue.UHD_BLURAY,
                SourceValue.BLURAY,
                SourceValue.HDTV,
                SourceValue.WEB_DL,
                SourceValue.WEBRIP,
                SourceValue.DVD,
                SourceValue.DVDRIP,
                SourceValue.HDCAM,
                SourceValue.R5,
                SourceValue.TC,
                SourceValue.TS,
                SourceValue.CAM,
            ],
            resource_form=[
                ResourceFormValue.BLURAY_DISC,
                ResourceFormValue.VIDEO_FILE,
                ResourceFormValue.DVD_DISC,
            ],
            hdr_type=[
                HdrTypeValue.DOLBY_VISION,
                HdrTypeValue.HDR10_PLUS,
                HdrTypeValue.HDR10,
            ],
            video_codec=[
                VideoCodecValue.HEVC,
                VideoCodecValue.AV1,
                VideoCodecValue.AVC,
            ],
            audio_codec=[
                AudioCodecValue.DOLBY_ATMOS,
                AudioCodecValue.DTS_X,
                AudioCodecValue.TRUEHD,
                AudioCodecValue.DTS_HD_MA,
                AudioCodecValue.DTS_HD,
                AudioCodecValue.DTS,
                AudioCodecValue.DDP,
                AudioCodecValue.AC3,
                AudioCodecValue.FLAC,
                AudioCodecValue.AAC,
            ],
            audio_channels=[
                AudioChannelsValue.CHANNELS_71,
                AudioChannelsValue.CHANNELS_51,
                AudioChannelsValue.CHANNELS_20,
                AudioChannelsValue.CHANNELS_10,
            ],
        )
