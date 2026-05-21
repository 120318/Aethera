import logging
from urllib.parse import ParseResult, urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_HOSTS = {
    "image.tmdb.org",
    "qnmob1.doubanio.com",
    "qnmob2.doubanio.com",
    "qnmob3.doubanio.com",
    "img1.doubanio.com",
    "img2.doubanio.com",
    "img3.doubanio.com",
    "img9.doubanio.com",
}
MAX_REDIRECTS = 5


def _parse_image_url(url: str) -> tuple[ParseResult, str]:
    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else None
    if parsed.scheme != "https" or not hostname:
        raise HTTPException(status_code=400, detail="invalid url")
    if hostname not in ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="disallowed host")
    return parsed, hostname


def _build_headers(hostname: str) -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.themoviedb.org/" if hostname == "image.tmdb.org" else "https://www.douban.com/",
    }


async def _close_stream(response: httpx.Response, client: httpx.AsyncClient) -> None:
    await response.aclose()
    await client.aclose()


async def _open_image_stream(url: str) -> tuple[httpx.Response, httpx.AsyncClient, str, dict[str, str]]:
    current_url = url
    redirect_count = 0

    client = httpx.AsyncClient(timeout=10.0)
    try:
        while True:
            _, hostname = _parse_image_url(current_url)
            request = client.build_request("GET", current_url, headers=_build_headers(hostname))
            response = await client.send(request, stream=True, follow_redirects=False)

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                await response.aclose()
                if not location:
                    await client.aclose()
                    raise HTTPException(status_code=502, detail="image fetch error")
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    await client.aclose()
                    raise HTTPException(status_code=400, detail="too many redirects")
                current_url = urljoin(current_url, location)
                continue

            if response.status_code != 200:
                status_code = response.status_code
                await response.aclose()
                await client.aclose()
                raise HTTPException(status_code=status_code, detail="failed to fetch image")

            content_type = response.headers.get("content-type", "application/octet-stream")
            if not content_type.startswith("image/"):
                await response.aclose()
                await client.aclose()
                raise HTTPException(status_code=502, detail="invalid image response")

            cache_headers = {
                "Cache-Control": response.headers.get("cache-control", "public, max-age=86400"),
            }
            if response.headers.get("etag"):
                cache_headers["ETag"] = response.headers["etag"]
            if response.headers.get("last-modified"):
                cache_headers["Last-Modified"] = response.headers["last-modified"]

            return response, client, content_type, cache_headers
    except HTTPException:
        raise
    except httpx.HTTPError:
        await client.aclose()
        raise


@router.get("/image")
async def proxy_image(url: str = Query(..., description="Remote image URL to proxy")) -> StreamingResponse:
    try:
        response, client, content_type, cache_headers = await _open_image_stream(url)
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=content_type,
            headers=cache_headers,
            background=BackgroundTask(_close_stream, response, client),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.debug("image proxy error: %s", exc)
        raise HTTPException(status_code=502, detail="image fetch error")
