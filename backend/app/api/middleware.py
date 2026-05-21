from __future__ import annotations

import json
import logging

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.types import ASGIApp

from app.schemas.exception import AppException
from app.schemas.exception.exceptions import SYSTEM_ERROR_CODE, SYSTEM_ERROR_KEY


def _is_json_response(headers: list[tuple[bytes, bytes]]) -> bool:
    for key, value in headers:
        if key.lower() == b"content-type":
            return b"application/json" in value.lower()
    return False


def _replace_or_append_header(headers: list[tuple[bytes, bytes]], key: bytes, value: bytes) -> list[tuple[bytes, bytes]]:
    out = [(k, v) for k, v in headers if k.lower() != key.lower()]
    out.append((key, value))
    return out


def _build_wrapped_body(body_bytes: bytes) -> bytes:
    original_data = json.loads(body_bytes.decode("utf-8"))
    if isinstance(original_data, dict) and "code" in original_data and "message_key" in original_data:
        original_data.setdefault("is_system_error", False)
        original_data.setdefault("params", {})
        return json.dumps(original_data, ensure_ascii=False).encode("utf-8")
    wrapped = {
        "code": 0,
        "message_key": None,
        "params": {},
        "data": original_data,
        "is_system_error": False,
    }
    return json.dumps(wrapped, ensure_ascii=False).encode("utf-8")


def _jsonable_error_data(data):
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    return data


class ResponseWrapperASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        if path.startswith("/api/v1/media/image"):
            await self.app(scope, receive, send)
            return

        response_start = None
        body_chunks: list[bytes] = []
        should_wrap = False

        async def send_wrapper(message) -> None:
            nonlocal response_start, should_wrap
            message_type = message.get("type")

            if message_type == "http.response.start":
                response_start = dict(message)
                raw_headers = list(response_start.get("headers", []))
                should_wrap = _is_json_response(raw_headers)
                return

            if message_type == "http.response.body" and response_start is not None:
                body_chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return

                body_bytes = b"".join(body_chunks)
                if should_wrap and body_bytes:
                    try:
                        body_bytes = _build_wrapped_body(body_bytes)
                        raw_headers = list(response_start.get("headers", []))
                        raw_headers = _replace_or_append_header(raw_headers, b"content-length", str(len(body_bytes)).encode("ascii"))
                        response_start["headers"] = raw_headers
                        response_start["status"] = 200
                    except Exception:
                        pass

                await send(response_start)
                await send({"type": "http.response.body", "body": body_bytes, "more_body": False})
                return

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            code = SYSTEM_ERROR_CODE
            message_key = SYSTEM_ERROR_KEY
            params = {}
            is_system_error = True
            if isinstance(exc, AppException):
                code = exc.code
                message_key = exc.message_key
                params = exc.params
                is_system_error = exc.is_system_error
                data = _jsonable_error_data(exc.data)
            else:
                logging.getLogger(__name__).exception("APItext: %s", exc)
                data = None

            response = JSONResponse(
                content={
                    "code": code,
                    "message_key": message_key,
                    "params": params,
                    "data": data,
                    "is_system_error": is_system_error,
                },
                status_code=200,
            )
            await response(scope, receive, send)
