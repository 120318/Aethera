import httpx
import pytest

from app.services.integration.notifications.channels.telegram import client as telegram_client_module
from app.services.integration.notifications.channels.telegram.client import TelegramClient


class FakeTelegramResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeAsyncClient:
    response_payload = {"ok": True}
    raised_exception = None
    seen_requests = []

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json):
        self.seen_requests.append((url, json))
        if self.raised_exception is not None:
            raise self.raised_exception
        return FakeTelegramResponse(self.response_payload)


@pytest.fixture(autouse=True)
def fake_async_client(monkeypatch):
    FakeAsyncClient.response_payload = {"ok": True}
    FakeAsyncClient.raised_exception = None
    FakeAsyncClient.seen_requests = []
    monkeypatch.setattr(telegram_client_module.httpx, "AsyncClient", FakeAsyncClient)


@pytest.mark.asyncio
async def test_telegram_connection_sends_test_message():
    result = await TelegramClient().test_connection(bot_token="123:token", chat_id="chat")

    assert result is True
    assert FakeAsyncClient.seen_requests == [
        (
            "https://api.telegram.org/bot123:token/sendMessage",
            {
                "chat_id": "chat",
                "text": "[Aethera] Notification test",
                "disable_web_page_preview": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_telegram_connection_returns_false_on_api_error():
    FakeAsyncClient.response_payload = {"ok": False, "description": "chat not found"}

    result = await TelegramClient().test_connection(bot_token="123:token", chat_id="missing")

    assert result is False


@pytest.mark.asyncio
async def test_telegram_connection_returns_false_on_invalid_token_format():
    result = await TelegramClient().test_connection(bot_token="invalid-token", chat_id="chat")

    assert result is False
    assert FakeAsyncClient.seen_requests == []


@pytest.mark.asyncio
async def test_telegram_connection_or_raise_reports_api_error():
    FakeAsyncClient.response_payload = {"ok": False, "description": "chat not found"}

    with pytest.raises(RuntimeError) as exc_info:
        await TelegramClient().test_connection_or_raise(bot_token="123:token", chat_id="missing")

    assert str(exc_info.value) == "chat not found"


@pytest.mark.asyncio
async def test_telegram_send_message_does_not_leak_bot_token_on_transport_error():
    request = httpx.Request("POST", "https://api.telegram.org/botsecret-token/sendMessage")
    FakeAsyncClient.raised_exception = httpx.RequestError("network failed", request=request)

    with pytest.raises(RuntimeError) as exc_info:
        await TelegramClient().send_message(bot_token="secret-token", chat_id="chat", text="hello")

    assert str(exc_info.value) == "Telegram API request failed"
    assert "secret-token" not in str(exc_info.value)
