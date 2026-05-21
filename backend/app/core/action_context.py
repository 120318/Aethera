from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional


_current_action_id: ContextVar[Optional[str]] = ContextVar("current_action_id", default=None)


def get_current_action_id() -> Optional[str]:
    return _current_action_id.get()


@contextmanager
def action_context(action_id: Optional[str]) -> Iterator[None]:
    token = _current_action_id.set(action_id)
    try:
        yield
    finally:
        _current_action_id.reset(token)
