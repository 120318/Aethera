import json
from datetime import datetime

from app.schemas.domain.event import Event, EventLevel, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.integration.notifications.channels.telegram.renderer import format_telegram_event


def _media() -> MediaIdentity:
    return MediaIdentity(
        media_id=MediaID.parse("tmdb:tv:273240"),
        title="校园之外",
        year=2026,
        season_number=1,
    )


def test_telegram_download_completed_uses_user_summary_in_zh_cn():
    event = Event(
        type=EventType.DOWNLOAD_COMPLETED,
        level=EventLevel.info,
        media=_media(),
        task_id="task-1",
        ts=datetime(2026, 6, 2, 20, 30),
        meta=json.dumps(
            {
                "resource_title": "Off.Campus.S01.2160p.AMZN.WEB-DL",
                "selected_episodes": [1, 2, 3],
                "task_id": "task-1",
            },
            ensure_ascii=False,
        ),
    )

    message = format_telegram_event(event, locale="zh-CN", public_base_url="https://ae.example.com/")

    assert "\\[Aethera\\]" in message
    assert "下载已完成" in message
    assert "校园之外" in message
    assert "第 1 季" in message
    assert "第 1\\-3 集" in message
    assert "资源：" in message
    assert "时间：2026\\-06\\-02 20:30" in message
    assert "查看详情" in message
    assert "https://ae\\.example\\.com/media/tmdb:tv:273240?season\\=1" in message
    assert "season\\_number" not in message
    assert "download.completed" not in message
    assert "task-1" not in message
    assert "meta:" not in message


def test_telegram_failed_event_uses_locale_and_reason():
    event = Event(
        type=EventType.MEDIA_IMPORT_FAILED,
        level=EventLevel.error,
        media=_media(),
        ts=datetime(2026, 6, 2, 20, 30),
        meta=json.dumps(
            {
                "resource_title": "Off.Campus.S01.2160p.AMZN.WEB-DL",
                "error_key": "backendErrors.transferFailed",
                "error_params": {"reason": "source missing"},
            },
            ensure_ascii=False,
        ),
    )

    message = format_telegram_event(event, locale="en-US", public_base_url="")

    assert "\\[Aethera\\]" in message
    assert "Import failed" in message
    assert "Season 1" in message
    assert "Reason: Transfer failed: source missing" in message
    assert "View details" not in message
    assert "media.import.failed" not in message
