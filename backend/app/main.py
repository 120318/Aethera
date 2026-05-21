import faulthandler
import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.exception_handlers import handle_http_exception, handle_request_validation_error
from app.api.v1.api import api_router
from app.api.auth_middleware import AuthASGIMiddleware
from app.api.http_timing_middleware import HttpTimingASGIMiddleware
from app.api.middleware import ResponseWrapperASGIMiddleware
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from app.db.migration_guard import assert_database_schema_is_current
from app.core.logging_config import setup_logging
from app.services.domain.download import download_service
from app.services.domain.subscription.repair_service import subscription_repair_service
from app.services.platform.auth_service import auth_service
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.audit.event_service import event_service
from app.addons.registry import addon_service
from app.services.application.workflows.media_server_sync import register_media_server_sync

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app")
FRONTEND_DIST = Path(os.getenv("AETHERA_FRONTEND_DIST", "/app/frontend_dist"))

try:
    faulthandler.enable(file=sys.stderr, all_threads=True)
except Exception:
    logger.exception("Failed to enable faulthandler")

try:
    faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)
except Exception:
    logger.exception("Failed to register SIGUSR1 faulthandler")


def _resolve_cors_origins() -> list[str]:
    configured = os.getenv("AETHERA_CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    backend_mode = (os.getenv("BACKEND_MODE", "dev") or "dev").lower()
    if backend_mode == "prod":
        return []
    return [
        "http://localhost:8173",
        "http://127.0.0.1:8173",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Internal helper."""
    # ── Startup ──
    logger.info("Application startup: pid=%s ppid=%s", os.getpid(), os.getppid())
    assert_database_schema_is_current()
    await subscription_repair_service.repair_missing_media_snapshots()

    try:
        if not auth_service.is_initialized():
            init_password = os.getenv("AETHERA_ADMIN_PASSWORD") or os.getenv("AUTOMOVIE_ADMIN_PASSWORD")
            if init_password:
                auth_service.set_password(init_password)
                bootstrap_service.recompute_status()
                logger.info("Admin password initialized from environment")
    except Exception as e:
        logger.error(f"Failed to initialize admin password: {e}")

    auth_provider_service.discover_and_register()
    # Internal note.
    addon_service.discover_and_register()
    register_media_server_sync()

    # Recover task runtime locks left by interrupted transfer workers.
    try:
        await download_service.recover_stuck_transferring_tasks(force=True)
    except Exception as e:
        logger.error(f"Failed to recover stuck transferring tasks on startup: {e}")

    logger.info("Application startup complete")

    yield

    # ── Shutdown ──
    logger.info("Application shutdown complete: pid=%s", os.getpid())


app = FastAPI(title="Aethera Backend", lifespan=lifespan)

app.add_middleware(AuthASGIMiddleware)
app.add_middleware(ResponseWrapperASGIMiddleware)
cors_origins = _resolve_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(HttpTimingASGIMiddleware)

# include versioned API routers
app.include_router(api_router)

app.add_exception_handler(RequestValidationError, handle_request_validation_error)
app.add_exception_handler(StarletteHTTPException, handle_http_exception)

@app.get("/", include_in_schema=False)
async def redirect_root() -> RedirectResponse:
    return RedirectResponse(url="/discover")


@app.get("/media", include_in_schema=False)
async def redirect_media_index() -> RedirectResponse:
    return RedirectResponse(url="/discover")


@app.get("/media/results", include_in_schema=False)
async def redirect_media_results(request: Request) -> RedirectResponse:
    query = request.url.query
    return RedirectResponse(url=f"/discover?{query}" if query else "/discover")


@app.get("/resources/manage", include_in_schema=False)
async def redirect_resource_manage() -> RedirectResponse:
    return RedirectResponse(url="/media-management")


@app.get("/resources", include_in_schema=False)
async def redirect_resources() -> RedirectResponse:
    return RedirectResponse(url="/media-management")


@app.get("/config", include_in_schema=False)
async def redirect_config() -> RedirectResponse:
    return RedirectResponse(url="/settings")


@app.get("/detail", include_in_schema=False)
async def redirect_detail(request: Request) -> RedirectResponse:
    media_id = request.query_params.get("media_id") or request.query_params.get("id")
    tab = request.query_params.get("tab")
    if not media_id:
        return RedirectResponse(url="/discover")
    query = f"?tab={tab}" if tab else ""
    return RedirectResponse(url=f"/media/{media_id}{query}")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> FileResponse:
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404)

    index_path = FRONTEND_DIST / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404)

    target_path = (FRONTEND_DIST / full_path).resolve()
    frontend_root = FRONTEND_DIST.resolve()
    if target_path.is_file() and (target_path == frontend_root or frontend_root in target_path.parents):
        return FileResponse(target_path)
    return FileResponse(index_path)
