from app.schemas.config import TelegramNotificationChannelConfig
from app.services.integration.notifications.channels.telegram.client import TelegramClient
from app.services.config.settings_service import settings_service
from app.services.i18n.message_renderer import render_message


async def test_telegram_connection_for_config(config: TelegramNotificationChannelConfig) -> bool:
    if not config.bot_token or not config.chat_id:
        return False
    locale = settings_service.get_base_system_config().locale
    await TelegramClient().test_connection_or_raise(
        bot_token=config.bot_token,
        chat_id=config.chat_id,
        text=render_message("telegram.testMessage", locale=locale),
    )
    return True


__all__ = ["test_telegram_connection_for_config"]
