from __future__ import annotations

import os

TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def env_flag_enabled(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUTHY_ENV_VALUES


def oidc_auth_enabled() -> bool:
    return env_flag_enabled("AETHERA_EXPERIMENTAL_OIDC_AUTH")


def telegram_notifications_enabled() -> bool:
    return env_flag_enabled("AETHERA_EXPERIMENTAL_TELEGRAM_NOTIFICATIONS")
