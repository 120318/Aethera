from __future__ import annotations

import logging
import time

from app.core.logging_config import is_trace_enabled
from app.core.request_perf_context import begin_request_perf, finish_request_perf
from starlette.types import ASGIApp

logger = logging.getLogger("app.http_timing")
SLOW_REQUEST_WARNING_THRESHOLD_MS = 100
SLOW_REQUEST_WARNING_EXCLUDED_PREFIXES = (
    "/api/v1/media/image",
)


class HttpTimingASGIMiddleware:
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

        started_at = time.monotonic()
        response_status = 500
        perf_token = begin_request_perf()

        async def send_wrapper(message) -> None:
            nonlocal response_status
            if message.get("type") == "http.response.start":
                response_status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
            perf_stats = finish_request_perf(perf_token)
            route = scope.get("route")
            route_path = getattr(route, "path", None) or path
            query_present = bool(scope.get("query_string"))
            method = scope.get("method", "GET")
            db_duration_ms = perf_stats.db_duration_ms if perf_stats else 0.0
            db_queries = perf_stats.db_queries if perf_stats else 0
            slow_db_queries = perf_stats.slow_db_queries if perf_stats else 0
            top_db_sources = perf_stats.top_db_sources_summary() if perf_stats else "-"
            if is_trace_enabled("app.http_timing"):
                logger.trace(
                    "http_timing method=%s route=%s status=%s duration_ms=%s db_duration_ms=%.1f db_queries=%s slow_db_queries=%s db_top_sources=%s path=%s query_present=%s",
                    method,
                    route_path,
                    response_status,
                    duration_ms,
                    db_duration_ms,
                    db_queries,
                    slow_db_queries,
                    top_db_sources,
                    path,
                    str(query_present).lower(),
                )
            if duration_ms > SLOW_REQUEST_WARNING_THRESHOLD_MS and not any(
                path.startswith(prefix) for prefix in SLOW_REQUEST_WARNING_EXCLUDED_PREFIXES
            ):
                logger.warning(
                    "slow_http_request method=%s route=%s status=%s duration_ms=%s db_duration_ms=%.1f db_queries=%s slow_db_queries=%s db_top_sources=%s path=%s query_present=%s threshold_ms=%s",
                    method,
                    route_path,
                    response_status,
                    duration_ms,
                    db_duration_ms,
                    db_queries,
                    slow_db_queries,
                    top_db_sources,
                    path,
                    str(query_present).lower(),
                    SLOW_REQUEST_WARNING_THRESHOLD_MS,
                )
