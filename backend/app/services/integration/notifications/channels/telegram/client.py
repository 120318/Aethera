from __future__ import annotations

import logging
from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("app.integration.notifications.channels.telegram.client")


class TelegramSendMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    description: str = ""


class TelegramClient:
    async def test_connection(self, bot_token: str, chat_id: str, text: str = "[Aethera] Notification test") -> bool:
        try:
            await self.test_connection_or_raise(bot_token=bot_token, chat_id=chat_id, text=text)
        except RuntimeError:
            return False
        return True

    async def test_connection_or_raise(self, bot_token: str, chat_id: str, text: str = "[Aethera] Notification test") -> None:
        self._validate_test_inputs(bot_token=bot_token, chat_id=chat_id)
        await self._post_api(
            bot_token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )

    async def send_message(self, bot_token: str, chat_id: str, text: str) -> None:
        await self._post_api(
            bot_token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
        )

    async def _post_api(self, bot_token: str, method: str, payload: Mapping[str, str | bool]) -> TelegramSendMessageResponse:
        url = f"https://api.telegram.org/bot{bot_token}/{method}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise RuntimeError("Telegram API request failed") from exc
        try:
            result = TelegramSendMessageResponse.model_validate(response.json())
        except ValueError as exc:
            raise RuntimeError("Telegram API returned an invalid response") from exc
        if not result.ok:
            raise RuntimeError(result.description or "Telegram API returned an error")
        return result

    def _validate_test_inputs(self, bot_token: str, chat_id: str) -> None:
        token_prefix, separator, token_secret = bot_token.partition(":")
        if not separator or not token_prefix.isdigit() or not token_secret:
            raise RuntimeError("Telegram bot token format is invalid")
        if not chat_id.strip():
            raise RuntimeError("Telegram chat id is required")
