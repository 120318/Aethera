from __future__ import annotations

import json
from pathlib import Path

from app.schemas.domain.alert import AlertCategory, AlertRaiseRequest, AlertResolveRequest, AlertSeverity, AlertTargetType
from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID
from app.services.domain.alerts import alert_service


def _nested_message_params(params: dict[str, str] | None) -> str:
    if not params:
        return ""
    return json.dumps(
        {str(key): str(value) for key, value in params.items() if value is not None},
        ensure_ascii=False,
        sort_keys=True,
    )


def _reason_params(error: str = "", error_key: str | None = None) -> dict[str, str]:
    if error_key:
        return {"reason_key": error_key}
    if error:
        return {"reason": error}
    return {"reason_key": "common.unknownError"}


def raise_danmu_alert(
    *,
    media: MediaIdentity,
    video_path: Path,
    action_id: str | None,
    task_id: str | None,
    provider: str | None = None,
    error: str = "",
    error_key: str | None = None,
) -> None:
    target = video_path.name or str(video_path)
    message_params = {
        "target": target,
        "video_path_name": target,
        "video_path": str(video_path),
        "provider": provider or "",
        **_reason_params(error, error_key),
    }
    alert_service.raise_alert(
        AlertRaiseRequest(
            fingerprint=danmu_alert_fingerprint(video_path),
            severity=AlertSeverity.error,
            category=AlertCategory.danmu_generate,
            message_key="alertMessages.danmuGenerateFailed",
            message_params=message_params,
            target_type=AlertTargetType.danmu_sidecar,
            target_id=str(video_path),
            media=media,
            media_id=media.media_id,
            task_id=task_id,
            action_id=action_id,
        )
    )


def resolve_danmu_alert(video_path: Path) -> None:
    alert_service.resolve_alert(AlertResolveRequest(fingerprint=danmu_alert_fingerprint(video_path)))


def danmu_alert_fingerprint(video_path: Path) -> str:
    return f"danmu.generate:{video_path}"


def raise_media_server_sync_alert(
    *,
    media: MediaIdentity,
    file_path: str,
    media_server_id: str,
    task_id: str | None,
    error: str = "",
) -> None:
    target = Path(file_path).name or file_path or str(media.media_id)
    alert_service.raise_alert(
        AlertRaiseRequest(
            fingerprint=media_server_sync_alert_fingerprint(media_server_id, file_path, media.media_id),
            severity=AlertSeverity.error,
            category=AlertCategory.media_server_sync,
            message_key="alertMessages.mediaServerSyncFailed",
            message_params={
                "target": target,
                "file_path_name": target,
                "file_path": file_path,
                "reason": error or "",
            },
            target_type=AlertTargetType.library_file,
            target_id=file_path or str(media.media_id),
            media=media,
            media_id=media.media_id,
            task_id=task_id,
        )
    )


def resolve_media_server_sync_alert(*, media: MediaIdentity, file_path: str, media_server_id: str) -> None:
    alert_service.resolve_alert(
        AlertResolveRequest(fingerprint=media_server_sync_alert_fingerprint(media_server_id, file_path, media.media_id))
    )


def media_server_sync_alert_fingerprint(media_server_id: str, file_path: str, media_id: MediaID) -> str:
    target = file_path or str(media_id)
    return f"media_server_sync:{media_server_id}:{target}"


def raise_notification_alert(
    *,
    channel_id: str,
    channel_name: str,
    channel_type: str,
    event_type: str,
    event_id: str,
    media: MediaIdentity | None,
    media_id: MediaID | None,
    task_id: str | None,
    action_id: str | None,
    error: str,
) -> None:
    target = channel_name or channel_id
    alert_service.raise_alert(
        AlertRaiseRequest(
            fingerprint=notification_alert_fingerprint(channel_id),
            severity=AlertSeverity.error,
            category=AlertCategory.notification_send,
            message_key="alertMessages.notificationSendFailed",
            message_params={
                "target": target,
                "channel": target,
                "channel_type": channel_type,
                "event_type": event_type,
                "event_id": event_id,
                "reason": error,
            },
            target_type=AlertTargetType.notification_channel,
            target_id=channel_id,
            media=media,
            media_id=media.media_id if media else media_id,
            task_id=task_id,
            action_id=action_id,
        )
    )


def resolve_notification_alert(channel_id: str) -> None:
    alert_service.resolve_alert(AlertResolveRequest(fingerprint=notification_alert_fingerprint(channel_id)))


def notification_alert_fingerprint(channel_id: str) -> str:
    return f"notification.send:{channel_id}"


def raise_indexer_site_alert(
    *,
    indexer_id: str,
    indexer_name: str,
    site_id: str,
    site_name: str,
    consecutive_failures: int,
    error: str,
) -> None:
    indexer = indexer_name or indexer_id
    site = site_name or site_id
    alert_service.raise_alert(
        AlertRaiseRequest(
            fingerprint=indexer_site_alert_fingerprint(indexer_id, site_id),
            severity=AlertSeverity.error,
            category=AlertCategory.indexer_health,
            message_key="alertMessages.indexerSiteFailed",
            message_params={
                "target": f"{indexer} / {site}",
                "indexer": indexer,
                "site": site,
                "failures": str(consecutive_failures),
                "reason": error or "",
            },
            target_type=AlertTargetType.indexer_site,
            target_id=f"{indexer_id}:{site_id}",
        )
    )


def resolve_indexer_site_alert(indexer_id: str, site_id: str) -> None:
    alert_service.resolve_alert(
        AlertResolveRequest(fingerprint=indexer_site_alert_fingerprint(indexer_id, site_id))
    )


def indexer_site_alert_fingerprint(indexer_id: str, site_id: str) -> str:
    return f"indexer.health:{indexer_id}:{site_id}"
