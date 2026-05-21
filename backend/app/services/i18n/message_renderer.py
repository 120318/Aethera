from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


DEFAULT_LOCALE = "zh-CN"
LOCALE_DIR = Path(__file__).with_name("locales")
PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")


@lru_cache(maxsize=1)
def _load_catalogs() -> dict[str, dict[str, str]]:
    catalogs: dict[str, dict[str, str]] = {}
    for path in sorted(LOCALE_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if type(raw) is not dict:
            continue
        catalogs[path.stem] = {str(key): str(value) for key, value in raw.items()}
    return catalogs


def render_message(message_key: str | None, params: dict[str, str] | None = None, *, locale: str = DEFAULT_LOCALE) -> str:
    key = message_key or "eventMessages.generic"
    catalogs = _load_catalogs()
    default_catalog = catalogs[DEFAULT_LOCALE]
    catalog = catalogs[locale] if locale in catalogs else default_catalog
    template = catalog[key] if key in catalog else default_catalog[key] if key in default_catalog else _humanize_message_key(key)
    normalized_params = _normalize_params(params or {}, locale=locale)
    return PLACEHOLDER_PATTERN.sub(lambda match: normalized_params[match.group(1)] if match.group(1) in normalized_params else "", template)


def _normalize_params(params: dict[str, str], *, locale: str) -> dict[str, str]:
    normalized = dict(params)
    if not normalized.get("resource_title") and normalized.get("title"):
        normalized["resource_title"] = normalized["title"]
    if not normalized.get("torrent_name") and normalized.get("resource_title"):
        normalized["torrent_name"] = normalized["resource_title"]
    for name, value in list(normalized.items()):
        if not name.endswith("_key") or type(value) is not str:
            continue
        target_name = name[:-4]
        if target_name in normalized and normalized[target_name]:
            continue
        normalized[target_name] = render_message(value, _nested_params(normalized, target_name), locale=locale)
    return normalized


def _nested_params(params: dict[str, str], name: str) -> dict[str, str]:
    params_key = f"{name}_params"
    raw = params[params_key] if params_key in params else None
    if type(raw) is dict:
        return {str(key): str(value) for key, value in raw.items() if value is not None}
    if type(raw) is not str or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if type(parsed) is not dict:
        return {}
    return {str(key): str(value) for key, value in parsed.items() if value is not None}


def _humanize_message_key(key: str) -> str:
    tail = key.rsplit(".", 1)[-1]
    text = re.sub(r"(?<!^)([A-Z])", r" \1", tail).replace("_", " ").replace("-", " ")
    return text[:1].upper() + text[1:]
