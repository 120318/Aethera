from __future__ import annotations

from app.schemas.domain.media import MediaIdentity


def format_media_target_label(media: MediaIdentity) -> str:
    title = media.title.strip()
    return f"{title} ({media.year})"
