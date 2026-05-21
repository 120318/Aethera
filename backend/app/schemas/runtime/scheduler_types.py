from __future__ import annotations

from enum import Enum


class SchedulerJobSourceType(str, Enum):
    system = "system"
    addon = "addon"
    unknown = "unknown"


class SchedulerJobTriggerType(str, Enum):
    interval = "interval"
    cron = "cron"


class SchedulerConfigScope(str, Enum):
    system = "system"
    addon = "addon"
