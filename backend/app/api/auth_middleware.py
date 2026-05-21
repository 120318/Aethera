from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp

from app.api.exception_handlers import app_exception_content
from app.schemas.exception import AuthenticationRequiredException, OnboardingRequiredException, SetupRequiredException
from app.services.config.settings_service import settings_service
from app.services.platform.auth_service import auth_service
from app.services.config.bootstrap_service import bootstrap_service

ALLOWLIST_PREFIXES = (
    "/api/v1/auth/bootstrap-status",
    "/api/v1/auth/bootstrap",
    "/api/v1/auth/login",
    "/api/v1/auth/providers",
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
    "/api/v1/auth/set-password",
    "/api/v1/media/image",
)

BOOTSTRAP_ALLOWED_PREFIXES = (
    "/api/v1/config",
)


class AuthASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/v1/") or any(path.startswith(prefix) for prefix in ALLOWLIST_PREFIXES):
            await self.app(scope, receive, send)
            return

        if not auth_service.is_initialized():
            response = JSONResponse(
                content=app_exception_content(SetupRequiredException()),
                status_code=200,
            )
            await response(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        session = auth_service.current_session(request)
        if not session:
            response = JSONResponse(
                content=app_exception_content(AuthenticationRequiredException()),
                status_code=200,
            )
            await response(scope, receive, send)
            return

        if not settings_service.is_onboarding_enabled():
            await self.app(scope, receive, send)
            return

        status = bootstrap_service.get_status()
        if status.onboarding_enabled and not status.completed and not any(path.startswith(prefix) for prefix in BOOTSTRAP_ALLOWED_PREFIXES):
            response = JSONResponse(
                content=app_exception_content(OnboardingRequiredException()),
                status_code=200,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
