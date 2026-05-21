import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class TokensResponse(BaseModel):
    tokens: dict[str, str]


@router.get("/config/tokens", response_model=TokensResponse)
def list_tokens() -> TokensResponse:
    """Return available tokens and short descriptions for template help in UI."""
    tokens = {
        "Movie Title": "Resource or torrent title",
        "Title": "Alias of Movie Title",
        "Series Title": "Series title for TV templates",
        "Year": "Year parsed from title, metadata, or attributes",
        "ReleaseYear": "Alias of Year",
        "tmdbId": "TMDB ID when available",
        "imdbId": "IMDb ID when available",
        "Quality": "Resolution or quality, such as 1080p",
        "resolution": "Resolution, such as 1080p or 2160p",
        "Source": "Source, such as WEB-DL or BluRay",
        "Release Group": "Release group",
        "Group": "Alias of Release Group",
        "language": "Language",
        "audio": "Audio codec or audio metadata",
        "videoCodec": "Video codec, such as x264, x265, or HEVC",
        "container": "Container format, such as mkv or mp4",
        "size": "Torrent size in bytes",
        "runtime": "Runtime in minutes",
        "season": "Season number, supports padding like {season:00}",
        "episode": "Episode number, supports padding like {episode:00}",
        "seasonFolder": "Folder placeholder rendered as 'Season X'",
        "Episode Title": "Episode title when parsed",
    }
    return TokensResponse(tokens=tokens)
