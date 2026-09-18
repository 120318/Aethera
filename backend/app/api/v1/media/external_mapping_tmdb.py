from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import MediaIDParam
from app.schemas.domain.command import CommandRecord
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.application.workflows.media_external_mapping import media_external_mapping_application_service
from app.services.domain.media import media_service

router = APIRouter()


class AttachTMDBMappingRequest(BaseModel):
    tmdb_id: int = Field(..., gt=0)
    season_number: int | None = Field(default=None, gt=0)
    episode_count_override: int | None = Field(default=None, gt=0)


class AttachSourceTMDBMappingRequest(AttachTMDBMappingRequest):
    source: MediaSourceName
    source_id: str
    media_type: MediaType


class AttachSourceTMDBMappingResponse(BaseModel):
    media_id: MediaID


class AttachTMDBMappingResponse(BaseModel):
    media_id: MediaID
    command: CommandRecord


@router.post("/external-mapping/tmdb", response_model=AttachTMDBMappingResponse)
async def attach_tmdb_mapping(
    body: AttachTMDBMappingRequest,
    mid: MediaID = Depends(MediaIDParam),
) -> AttachTMDBMappingResponse:
    result = await media_external_mapping_application_service.attach_tmdb_mapping(
        mid,
        tmdb_id=body.tmdb_id,
        season_number=body.season_number,
        episode_count_override=body.episode_count_override,
    )
    return AttachTMDBMappingResponse(media_id=result.media_id, command=result.command)


@router.post("/external-mapping/tmdb/source", response_model=AttachSourceTMDBMappingResponse)
async def attach_source_tmdb_mapping(body: AttachSourceTMDBMappingRequest) -> AttachSourceTMDBMappingResponse:
    media_id = await media_service.attach_source_tmdb_mapping(
        MediaSourceLookup(source=body.source, source_id=body.source_id, media_type=body.media_type),
        tmdb_id=body.tmdb_id,
        season_number=body.season_number,
        episode_count_override=body.episode_count_override,
    )
    return AttachSourceTMDBMappingResponse(media_id=media_id)
