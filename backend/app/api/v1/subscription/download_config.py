from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import MediaIDParam
from app.api.v1.subscription.season_context import require_subscription_season
from app.schemas.domain.media_download_config import MediaDownloadConfigPatch, MediaDownloadConfigView
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.media_id import MediaID
from app.services.domain.subscription.download_config_service import subscription_download_config_service

router = APIRouter()


class DownloadConfigResponse(BaseModel):
    data: MediaDownloadConfigView


class DownloadConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] | None = None


@router.get("/download-config", response_model=DownloadConfigResponse)
async def get_download_config(
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> DownloadConfigResponse:
    season = require_subscription_season(mid, season_number)
    config = await subscription_download_config_service.find_by_media_id(mid, season)
    view = MediaDownloadConfigView(
        sub_id=config.sub_id if config else None,
        media_id=mid,
        season_number=season,
        directory_id=config.directory_id if config else None,
        filter_config_id=config.filter_config_id if config else None,
        quality_profile_id=config.quality_profile_id if config else None,
        filters=config.filters if config else None,
        sites=config.sites if config else None,
        unmatched_rules=list(config.unmatched_rules) if config else [],
    )
    return DownloadConfigResponse(data=view)


@router.put("/download-config", response_model=DownloadConfigResponse)
async def put_download_config(
    body: DownloadConfigUpdateRequest,
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> DownloadConfigResponse:
    season = require_subscription_season(mid, season_number)
    config = await subscription_download_config_service.patch(
        mid,
        MediaDownloadConfigPatch(
            directory_id=body.directory_id,
            filter_config_id=body.filter_config_id,
            quality_profile_id=body.quality_profile_id,
            filters=body.filters,
            sites=body.sites,
            unmatched_rules=body.unmatched_rules,
        ),
        season_number=season,
    )
    return DownloadConfigResponse(
        data=MediaDownloadConfigView(
            sub_id=config.sub_id,
            media_id=config.media_id,
            season_number=config.season_number,
            directory_id=config.directory_id,
            filter_config_id=config.filter_config_id,
            quality_profile_id=config.quality_profile_id,
            filters=config.filters,
            sites=config.sites,
            unmatched_rules=list(config.unmatched_rules),
        )
    )
