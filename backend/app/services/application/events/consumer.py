from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import EventConsumerExecutionException
from app.schemas.domain.action import ActionSource
from app.schemas.domain.event import Event

logger = logging.getLogger("app.event_consumer_service")


def event_pattern_matches(event_type: str, pattern: str) -> bool:
    if not pattern:
        return False
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-1])
    return event_type == pattern


def event_matches_patterns(event_type: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(event_pattern_matches(event_type, pattern) for pattern in patterns)


@dataclass(frozen=True)
class EventConsumerRegistration:
    name: str
    patterns: list[str]
    handler: Callable[[Event], Awaitable[None]]
    source_type: ActionSource = ActionSource.addon


class EventConsumerService:
    def __init__(self) -> None:
        self._consumers: dict[str, EventConsumerRegistration] = {}

    def register(
        self,
        *,
        name: str,
        patterns: list[str],
        handler: Callable[[Event], Awaitable[None]],
        source_type: ActionSource = ActionSource.addon,
    ) -> None:
        self._consumers[name] = EventConsumerRegistration(
            name=name,
            patterns=patterns,
            handler=handler,
            source_type=source_type,
        )
        logger.debug("Registered event consumer: %s", name)

    def list_consumers(self) -> list[EventConsumerRegistration]:
        return list(self._consumers.values())

    def get_consumer(self, name: str) -> EventConsumerRegistration | None:
        if name not in self._consumers:
            return None
        return self._consumers[name]

    def match_consumers(self, event_type: str) -> list[EventConsumerRegistration]:
        return [consumer for consumer in self._consumers.values() if event_matches_patterns(event_type, consumer.patterns)]

    async def dispatch(self, event: Event, consumer_name: str) -> None:
        consumer = self.get_consumer(consumer_name)
        if not consumer:
            raise ValueError(f"event consumer not found: {consumer_name}")

        try:
            await consumer.handler(event)
        except (AppException, RuntimeError, ValueError) as exc:
            raise EventConsumerExecutionException(consumer.name, str(exc)) from exc
        except Exception as exc:
            raise EventConsumerExecutionException(consumer.name, str(exc)) from exc


event_consumer_service = EventConsumerService()
