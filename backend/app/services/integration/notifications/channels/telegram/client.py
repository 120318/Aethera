from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("app.integration.notifications.channels.telegram.client")


class TelegramSendMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    description: str = ""


class TelegramClient:
    async def send_message(self, bot_token: str, chat_id: str, text: str) -> None:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = TelegramSendMessageResponse.model_validate(response.json())
            if not result.ok:
                raise RuntimeError(result.description or "Telegram API returned an error")
