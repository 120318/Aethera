import pytest

from app.schemas.domain.event import Event, EventType
from app.schemas.exception.exceptions import EventConsumerExecutionException
from app.services.application.events.consumer import EventConsumerService


@pytest.mark.asyncio
async def test_event_consumer_dispatch_does_not_create_action(monkeypatch):
    service = EventConsumerService()
    handled = []

    async def handler(event: Event) -> None:
        handled.append(event.id)

    create_action = monkeypatch.setattr(
        "app.services.audit.action_service.action_service.create_action",
        lambda **kwargs: pytest.fail("event dispatch must not create an action"),
    )
    assert create_action is None

    service.register(name="sample", patterns=[EventType.MEDIA_IMPORT_COMPLETED.value], handler=handler)
    event = Event(type=EventType.MEDIA_IMPORT_COMPLETED)

    await service.dispatch(event, "sample")

    assert handled == [event.id]


@pytest.mark.asyncio
async def test_event_consumer_dispatch_wraps_handler_errors():
    service = EventConsumerService()

    async def handler(event: Event) -> None:
        raise OSError("boom")

    service.register(name="sample", patterns=["*"], handler=handler)

    with pytest.raises(EventConsumerExecutionException):
        await service.dispatch(Event(type=EventType.MEDIA_IMPORT_COMPLETED), "sample")
