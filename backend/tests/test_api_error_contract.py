from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.auth_middleware import AuthASGIMiddleware
from app.api.exception_handlers import handle_http_exception, handle_request_validation_error
from app.api.middleware import ResponseWrapperASGIMiddleware
from app.schemas.exception.exceptions import (
    InvalidRequestException,
    SYSTEM_ERROR_CODE,
    SYSTEM_ERROR_MESSAGE,
)


def test_response_wrapper_wraps_business_exception() -> None:
    app = FastAPI()
    app.add_middleware(ResponseWrapperASGIMiddleware)

    @app.get("/api/v1/test")
    async def test_route():
        raise InvalidRequestException("bad request")

    with TestClient(app) as client:
        response = client.get("/api/v1/test")

    assert response.status_code == 200
    assert response.json() == {
        "code": 10013,
        "message": "bad request",
        "data": None,
        "is_system_error": False,
    }


def test_response_wrapper_wraps_unknown_exception_as_uniform_system_error() -> None:
    app = FastAPI()
    app.add_middleware(ResponseWrapperASGIMiddleware)

    @app.get("/api/v1/test")
    async def test_route():
        raise RuntimeError("boom")

    with TestClient(app) as client:
        response = client.get("/api/v1/test")

    assert response.status_code == 200
    assert response.json() == {
        "code": SYSTEM_ERROR_CODE,
        "message": SYSTEM_ERROR_MESSAGE,
        "data": None,
        "is_system_error": True,
    }


def test_media_image_path_skips_json_wrapper() -> None:
    app = FastAPI()
    app.add_middleware(ResponseWrapperASGIMiddleware)

    @app.get("/api/v1/media/image")
    async def media_image():
        raise HTTPException(status_code=400, detail="invalid url")

    with TestClient(app) as client:
        response = client.get("/api/v1/media/image")

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid url"}


def test_response_wrapper_normalizes_framework_validation_error() -> None:
    app = FastAPI()
    app.add_middleware(ResponseWrapperASGIMiddleware)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)

    @app.get("/api/v1/validate")
    async def validate_route(count: int):
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/api/v1/validate", params={"count": "oops"})

    assert response.status_code == 200
    assert response.json() == {
        "code": 10013,
        "message": "Sample",
        "data": None,
        "is_system_error": False,
    }


def test_response_wrapper_normalizes_framework_http_exception_via_exception_handler() -> None:
    app = FastAPI()
    app.add_middleware(ResponseWrapperASGIMiddleware)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)

    @app.get("/api/v1/fail")
    async def fail_route():
        raise HTTPException(status_code=404, detail="Sample")

    with TestClient(app) as client:
        response = client.get("/api/v1/fail")

    assert response.status_code == 200
    assert response.json() == {
        "code": 404,
        "message": "Sample",
        "data": None,
        "is_system_error": False,
    }


def test_auth_middleware_returns_setup_required_with_business_flag(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(AuthASGIMiddleware)

    @app.get("/api/v1/protected")
    async def protected():
        return {"ok": True}

    from app.api import auth_middleware as auth_module

    monkeypatch.setattr(auth_module.auth_service, "is_initialized", lambda: False)

    with TestClient(app) as client:
        response = client.get("/api/v1/protected")

    assert response.status_code == 200
    assert response.json() == {
        "code": 460,
        "message": "text，text",
        "data": None,
        "is_system_error": False,
    }


def test_auth_middleware_returns_not_logged_in_with_business_flag(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(AuthASGIMiddleware)

    @app.get("/api/v1/protected")
    async def protected():
        return {"ok": True}

    from app.api import auth_middleware as auth_module

    monkeypatch.setattr(auth_module.auth_service, "is_initialized", lambda: True)
    monkeypatch.setattr(auth_module.auth_service, "current_session", lambda request: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/protected")

    assert response.status_code == 200
    assert response.json() == {
        "code": 401,
        "message": "Sample",
        "data": None,
        "is_system_error": False,
    }


def test_auth_middleware_returns_onboarding_required_with_business_flag(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(AuthASGIMiddleware)

    @app.get("/api/v1/protected")
    async def protected():
        return {"ok": True}

    from app.api import auth_middleware as auth_module

    monkeypatch.setattr(auth_module.auth_service, "is_initialized", lambda: True)
    monkeypatch.setattr(auth_module.auth_service, "current_session", lambda request: SimpleNamespace(username="admin"))
    monkeypatch.setattr(auth_module.settings_service, "is_onboarding_enabled", lambda: True)
    monkeypatch.setattr(
        auth_module.bootstrap_service,
        "get_status",
        lambda: SimpleNamespace(onboarding_enabled=True, completed=False),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/protected")

    assert response.status_code == 200
    assert response.json() == {
        "code": 461,
        "message": "text，text",
        "data": None,
        "is_system_error": False,
    }
