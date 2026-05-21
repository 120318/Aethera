import logging
from pathlib import Path

import httpx

logger = logging.getLogger("app.utils.http_file")


async def download_url_to_file(url: str | None, dest_path: Path) -> bool:
    if not url or dest_path.exists():
        return False
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return False
        dest_path.write_bytes(response.content)
        logger.debug("Downloaded remote file: %s", dest_path)
        return True
    except (httpx.HTTPError, OSError) as exc:
        logger.error("Failed to download remote file %s: %s", url, exc)
        return False
