from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.schemas.exception.exceptions import InvalidCredentialsException, SetupRequiredException, SystemAlreadyInitializedException
from app.services.platform.auth_service import auth_service
from app.services.config.bootstrap_service import BootstrapStatus, bootstrap_service

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(default="admin")
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    logged_in: bool = True
    username: str = "admin"


class LogoutResponse(BaseModel):
    ok: bool = True


class BootstrapRequest(BaseModel):
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class BootstrapStatusResponse(BaseModel):
    initialized: bool
    onboarding_enabled: bool
    setup_required: bool
    completed: bool
    current_step: str
    password_ready: bool
    tmdb_ready: bool
    downloaders_ready: bool
    indexers_ready: bool
    directories_ready: bool
    templates_ready: bool
    logged_in: bool
    username: str | None = None


class MeResponse(BootstrapStatusResponse):
    pass


def build_bootstrap_response(status: BootstrapStatus, logged_in: bool, username: str | None) -> BootstrapStatusResponse:
    setup_required = (not status.password_ready) or (status.onboarding_enabled and not status.completed)
    return BootstrapStatusResponse(
        initialized=status.password_ready,
        onboarding_enabled=status.onboarding_enabled,
        setup_required=setup_required,
        completed=status.completed,
        current_step=status.current_step,
        password_ready=status.password_ready,
        tmdb_ready=status.tmdb_ready,
        downloaders_ready=status.downloaders_ready,
        indexers_ready=status.indexers_ready,
        directories_ready=status.directories_ready,
        templates_ready=status.templates_ready,
        logged_in=logged_in,
        username=username,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    if body.username != auth_service.USERNAME:
        raise InvalidCredentialsException()

    if not auth_service.is_initialized():
        raise SetupRequiredException()

    stored = auth_service.get_password_hash()
    if not stored or not auth_service.verify_password(body.password, stored):
        raise InvalidCredentialsException()

    sess = auth_service.issue_session()
    response.set_cookie(
        key=auth_service.COOKIE_NAME,
        value=sess.token,
        httponly=True,
        samesite="lax",
        secure=auth_service.is_https_request(request),
        max_age=auth_service.get_session_cookie_max_age_seconds(),
        path="/",
    )
    return LoginResponse(logged_in=True, username=sess.username)


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, response: Response) -> LogoutResponse:
    token = auth_service.extract_token(request)
    if token:
        auth_service.revoke_session(token)
    response.delete_cookie(key=auth_service.COOKIE_NAME, path="/")
    return LogoutResponse(ok=True)


@router.get("/me", response_model=MeResponse)
async def me(request: Request) -> MeResponse:
    status = bootstrap_service.get_status()
    sess = auth_service.current_session(request)
    if not sess:
        response = build_bootstrap_response(status, logged_in=False, username=None)
        return MeResponse.model_validate(response)
    response = build_bootstrap_response(status, logged_in=True, username=sess.username)
    return MeResponse.model_validate(response)


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def bootstrap_status(request: Request) -> BootstrapStatusResponse:
    status = bootstrap_service.get_status()
    sess = auth_service.current_session(request)
    return build_bootstrap_response(status, logged_in=bool(sess), username=sess.username if sess else None)


@router.post("/bootstrap", response_model=BootstrapStatusResponse)
async def bootstrap(body: BootstrapRequest, request: Request, response: Response) -> BootstrapStatusResponse:
    if auth_service.is_initialized():
        raise SystemAlreadyInitializedException()
    sess = auth_service.bootstrap(body.password)
    status = bootstrap_service.recompute_status()
    response.set_cookie(
        key=auth_service.COOKIE_NAME,
        value=sess.token,
        httponly=True,
        samesite="lax",
        secure=auth_service.is_https_request(request),
        max_age=auth_service.get_session_cookie_max_age_seconds(),
        path="/",
    )
    return build_bootstrap_response(status, logged_in=True, username=sess.username)


@router.post("/set-password", response_model=BootstrapStatusResponse)
async def set_password(body: BootstrapRequest, request: Request, response: Response) -> BootstrapStatusResponse:
    return await bootstrap(body, request, response)


@router.post("/change-password", response_model=LogoutResponse)
async def change_password(request: Request, body: ChangePasswordRequest) -> LogoutResponse:
    auth_service.require_session(request)
    auth_service.change_password(body.old_password, body.new_password)
    bootstrap_service.recompute_status()
    return LogoutResponse(ok=True)
