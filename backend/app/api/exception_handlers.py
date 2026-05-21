from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.exception.exceptions import InvalidRequestException


def should_use_json_api_error_contract(path: str) -> bool:
    return path.startswith("/api/") and not path.startswith("/api/v1/media/image")


def app_exception_content(exc) -> dict:
    return {
        "code": exc.code,
        "message_key": exc.message_key,
        "params": exc.params,
        "data": exc.data,
        "is_system_error": exc.is_system_error,
    }


async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not should_use_json_api_error_contract(request.url.path):
        return JSONResponse(content={"detail": exc.errors()}, status_code=422)

    app_exc = InvalidRequestException("backendErrors.invalidRequest")
    return JSONResponse(content=app_exception_content(app_exc), status_code=200)


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if not should_use_json_api_error_contract(request.url.path):
        return JSONResponse(content={"detail": exc.detail}, status_code=exc.status_code)

    return JSONResponse(
        content={
            "code": exc.status_code,
            "message_key": "backendErrors.http",
            "params": {},
            "data": None,
            "is_system_error": False,
        },
        status_code=200,
    )
