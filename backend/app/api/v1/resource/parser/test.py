"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser import ResourceParser

logger = get_logger(__name__)
router = APIRouter()

# Internal note.
resource_parser = ResourceParser()


class TestParserData(BaseModel):
    title: str
    parsed: ResourceAttributes | None = None
    error: str | None = None
    success: bool


class TestParserPayload(BaseModel):
    results: list[TestParserData] = Field(default_factory=list)


class TestParserResponse(BaseModel):
    data: TestParserPayload


@router.get("/test", response_model=TestParserResponse)
async def test_parser() -> TestParserResponse:
    """
    text
    """
    test_titles = [
        "[HDCTV] text Joy of Life S02E01-E04 2024 2160p WEB-DL HEVC AAC-HDCTV",
        "[HDSky] text Three Body Problem S01E01-E08 Complete 2024 2160p NF WEB-DL x265 10bit HDR DV Atmos-HDSky",
        "[CHD] Dune Part Two text2 2024 BluRay 2160p TrueHD Atmos 7.1 x265 10bit HDR DV-CHD",
        "[FRDS] text Blossoms S01 Complete 2023 2160p WEB-DL HEVC AAC-FRDS",
        "[AQLJ] text My Altay S01E01-E08 Complete 2024 2160p WEB-DL HEVC AAC-AQLJ",
        "[FRDS] The Bear S03E01-E10 Complete 2024 2160p DSNP WEB-DL DDP5.1 Atmos x265 10bit HDR-FRDS",
        "Movie.2024.2160p.UHD.BluRay.BD100",
        "Movie.1999.DVD9.VIDEO_TS",
        "Show.S01.Disc.1.of.2.1080p.BluRay.AVC.DTS-HD.MA",
    ]
    
    results: list[TestParserData] = []
    
    for title in test_titles:
        attributes = resource_parser.parse(title)
        results.append(
            TestParserData(
                title=title,
                parsed=ResourceAttributes(
                    groups=attributes.groups,
                    resolution=attributes.resolution,
                    video_codec=attributes.video_codec,
                    audio_codec=attributes.audio_codec,
                    hdr_type=attributes.hdr_type,
                    sources=attributes.sources,
                    resource_form=attributes.resource_form,
                    seasons=attributes.seasons,
                    episodes=attributes.episodes,
                    disc_number=attributes.disc_number,
                    disc_total=attributes.disc_total,
                    content_type=attributes.content_type,
                ),
                success=True,
            )
        )
    
    return TestParserResponse(
        data=TestParserPayload(results=results)
    )
