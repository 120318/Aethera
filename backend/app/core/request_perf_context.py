from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field


@dataclass(slots=True)
class RequestPerformanceStats:
    db_queries: int = 0
    db_duration_ms: float = 0.0
    slow_db_queries: int = 0
    db_source_queries: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    db_source_duration_ms: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def record_db_query(self, source: str, duration_ms: float) -> None:
        self.db_queries += 1
        self.db_duration_ms += duration_ms
        self.db_source_queries[source] += 1
        self.db_source_duration_ms[source] += duration_ms

    def top_db_sources_summary(self, limit: int = 3) -> str:
        if not self.db_source_queries:
            return "-"
        ranked_sources = sorted(
            self.db_source_queries,
            key=lambda source: (-self.db_source_queries[source], -self.db_source_duration_ms[source], source),
        )
        return ",".join(
            f"{source}:{self.db_source_queries[source]}/{self.db_source_duration_ms[source]:.1f}ms"
            for source in ranked_sources[:limit]
        )


_current_request_perf: ContextVar[RequestPerformanceStats | None] = ContextVar("current_request_perf", default=None)
_current_db_source: ContextVar[str | None] = ContextVar("current_db_source", default=None)


def begin_request_perf() -> Token:
    return _current_request_perf.set(RequestPerformanceStats())


def finish_request_perf(token: Token) -> RequestPerformanceStats | None:
    stats = _current_request_perf.get()
    _current_request_perf.reset(token)
    return stats


def get_request_perf() -> RequestPerformanceStats | None:
    return _current_request_perf.get()


def get_current_db_source() -> str | None:
    return _current_db_source.get()


@contextmanager
def db_perf_source(source: str):
    token = _current_db_source.set(source)
    try:
        yield
    finally:
        _current_db_source.reset(token)
