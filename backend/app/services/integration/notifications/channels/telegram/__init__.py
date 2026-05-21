from app.core.feature_flags import telegram_notifications_enabled

if telegram_notifications_enabled():
    from app.services.integration.notifications.channels.telegram.channel import TelegramNotificationChannel
    from app.services.platform.notification_channel_service import notification_channel_service

    notification_channel_service.register(TelegramNotificationChannel())
