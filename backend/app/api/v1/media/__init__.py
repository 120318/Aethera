"""Media subpackage for API v1.

This package contains media-related endpoints split into `search` and `detail` modules.
"""
from app.api.v1.media import search, detail, detail_page, detail_overview, operations, proxy_image, external_mapping_tmdb, profile_refresh  # noqa: F401
from fastapi import APIRouter

# Define router and logger first so submodules can import them
# without triggering circular imports when this package is imported.
router = APIRouter(prefix="/media")

# Import endpoint modules after router/logger are defined so their
# routers are available to be included on the package router.

# Include the submodule routers
router.include_router(detail.router)
router.include_router(detail_page.router)
router.include_router(detail_overview.router)
router.include_router(operations.router)
router.include_router(search.router)
router.include_router(proxy_image.router)
router.include_router(external_mapping_tmdb.router)
router.include_router(profile_refresh.router)
