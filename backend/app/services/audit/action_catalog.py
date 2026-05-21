from __future__ import annotations

from app.schemas.domain.action import ActionKind, ActionName, ActionSource, ActionStatus, ActionTrigger

ACTION_NAME_EVENT_DISPATCH = ActionName.event_dispatch
ACTION_NAME_NOTIFICATION_SEND = ActionName.notification_send
ACTION_NAME_DANMU_GENERATE = ActionName.danmu_generate

SCHEDULER_JOB_SYNC_ACTIVE_DOWNLOADS = ActionName.sync_active_downloads.value
SCHEDULER_JOB_PROCESS_COMPLETED_TASKS = ActionName.process_completed_tasks.value
SCHEDULER_JOB_SUBSCRIPTION_SWEEP = ActionName.subscription_sweep.value
SCHEDULER_JOB_SCHEDULE_REFRESH_SWEEP = ActionName.schedule_refresh_sweep.value
SCHEDULER_JOB_DIRECTORY_INTEGRITY_AUDIT = ActionName.directory_integrity_audit.value
SCHEDULER_JOB_CLEANUP_INACTIVE_MANAGED_MEDIA_PROFILES = ActionName.cleanup_inactive_managed_media_profiles.value
SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP = ActionName.media_server_sync_incremental_sweep.value
SCHEDULER_JOB_CLEANUP_EXPIRED_SESSIONS = ActionName.cleanup_expired_sessions.value

ACTION_FILTER_KINDS: tuple[str, ...] = tuple(kind.value for kind in ActionKind)
ACTION_FILTER_STATUSES: tuple[str, ...] = tuple(status.value for status in ActionStatus)
ACTION_FILTER_TRIGGERS: tuple[str, ...] = tuple(trigger.value for trigger in ActionTrigger)
ACTION_FILTER_SOURCES: tuple[str, ...] = tuple(source.value for source in ActionSource)

SYSTEM_SCHEDULER_ACTION_NAMES: tuple[str, ...] = (
    SCHEDULER_JOB_SYNC_ACTIVE_DOWNLOADS,
    SCHEDULER_JOB_PROCESS_COMPLETED_TASKS,
    SCHEDULER_JOB_SUBSCRIPTION_SWEEP,
    SCHEDULER_JOB_SCHEDULE_REFRESH_SWEEP,
    SCHEDULER_JOB_DIRECTORY_INTEGRITY_AUDIT,
    SCHEDULER_JOB_CLEANUP_INACTIVE_MANAGED_MEDIA_PROFILES,
    SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP,
    SCHEDULER_JOB_CLEANUP_EXPIRED_SESSIONS,
)

ADDON_ACTION_NAMES: tuple[str, ...] = (
    ACTION_NAME_EVENT_DISPATCH,
    ACTION_NAME_NOTIFICATION_SEND,
    ACTION_NAME_DANMU_GENERATE,
)

ACTION_FILTER_ACTION_NAMES: tuple[str, ...] = tuple(action_name.value for action_name in ActionName)

SYSTEM_JOB_CONFIG_FIELDS: dict[str, str] = {
    SCHEDULER_JOB_SYNC_ACTIVE_DOWNLOADS: "sync_active_downloads_interval_seconds",
    SCHEDULER_JOB_PROCESS_COMPLETED_TASKS: "process_completed_tasks_interval_seconds",
    SCHEDULER_JOB_SUBSCRIPTION_SWEEP: "subscription_sweep_interval_seconds",
    SCHEDULER_JOB_SCHEDULE_REFRESH_SWEEP: "schedule_refresh_sweep_interval_seconds",
    SCHEDULER_JOB_DIRECTORY_INTEGRITY_AUDIT: "directory_integrity_audit_interval_seconds",
    SCHEDULER_JOB_CLEANUP_INACTIVE_MANAGED_MEDIA_PROFILES: "cleanup_inactive_managed_media_profiles_interval_seconds",
    SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP: "mediaserver",
    SCHEDULER_JOB_CLEANUP_EXPIRED_SESSIONS: "cleanup_expired_sessions_interval_seconds",
}
