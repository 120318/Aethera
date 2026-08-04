from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "app"
API_V1_ROOT = BACKEND_ROOT / "api" / "v1"
FRONTEND_API_ROOT = Path(os.environ.get("AETHERA_FRONTEND_API_ROOT", REPO_ROOT.parent / "frontend" / "src" / "api"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

API_MAX_LINES = 160
SERVICE_MAX_LINES = 600

# config_service text，text.
CONFIG_SERVICE_ALLOWLIST_REASONS: dict[str, str] = {}

# API middleware text，text BaseResponse text.
API_BASE_RESPONSE_IMPORT_ALLOWLIST_REASONS = {
    "app/api/middleware.py": "Sample",
}

# middleware text；text JSON text/text，text HTTP text.
JSON_API_HTTP_EXCEPTION_ALLOWLIST_REASONS = {
    "app/api/middleware.py": "text HTTPException",
    "app/api/v1/media/proxy_image.py": "text JSON text，text HTTP text",
}

# Internal note.
MEDIA_INFO_FULL_ALLOWLIST_REASONS = {
    "app/services/application/views/media_detail/service.py": "Sample",
    "app/services/application/views/media_detail_overview/service.py": "Sample",
    "app/services/application/views/media_detail_page/service.py": "detail page resolves the effective TV season from full media details before loading scoped view data",
    "app/services/application/workflows/media_server_sync/service.py": "text,text",
    "app/services/application/workflows/media_server_sync/season_runner.py": "season-scoped media server sync runner loads media details before metadata refresh",
    "app/services/application/workflows/media_server_sync/pipeline.py": "text metadata enrich text provider client text",
    "app/services/application/workflows/danmu/source_resolver.py": "danmu workflow resolves fetchable media and season-scoped platform sources",
    "app/api/v1/calendar/airings.py": "Sample",
    "app/api/v1/library/list.py": "Sample",
    "app/api/v1/library/overview.py": "Sample",
}

MEDIA_REFRESH_ALLOWLIST_REASONS = {
    "app/services/application/views/calendar/service.py": "Sample",
    "app/services/application/commands/handlers/profile.py": "Sample",
    "app/services/application/workflows/danmu/source_resolver.py": "danmu workflow weakly refreshes season-scoped media before checking fetchable platforms",
    "app/services/domain/media/profile/service.py": "text profile text",
    "app/services/domain/media/service.py": "text facade",
    "app/services/domain/transfer/service.py": "text，text",
}

PROVIDER_DETAIL_READ_ALLOWLIST_REASONS = {
    "app/services/domain/media/profile/service.py": "profile miss text",
    "app/services/domain/media/profile/refresh.py": "text profile refresh text provider text",
}

DISALLOWED_LOG_MESSAGE_PATTERNS = (
    (re.compile(r"[📜🎬✅❌🚀🔥]"), "text emoji text"),
    (re.compile(r"FILTERED OUT|PASSED filter"), "Sample"),
    (re.compile(r"Attempting to "), "text Attempting to text"),
)

DISALLOWED_PATTERNS = (
    r"\bisinstance\s*\(",
    r"MediaID\.parse\(",
    r"getattr\(",
    r"hasattr\(",
    r"\*\*kwargs",
    r"\.dict\(",
    r"\bobject\b",
)

MEDIA_YEAR_STR_ALLOWLIST_REASONS = {
    "app/addons/registry.py": "CronSpec.year text APScheduler cron text，text",
}

DISALLOWED_PATTERN_ALLOWLIST_REASONS = {
    r"\bisinstance\s*\(": {
        "app/services/domain/resource/torrent_metadata.py": "torrent bencode text bencodepy text OrderedDict/dict text",
    },
}

APPLICATION_REPOSITORY_IMPORT_ALLOWLIST_REASONS = {
    "app/services/application/commands/service.py": "application command queue runtime state",
    "app/services/application/events/dispatch.py": "application event dispatch queue runtime state",
    "app/services/application/workflows/media_server_sync/state.py": "media server sync workflow runtime state",
}


def allowlist_paths(allowlist: dict[str, str]) -> set[str]:
    return set(allowlist)


def check_allowlist_integrity() -> list[Finding]:
    findings: list[Finding] = []
    allowlists = (
        ("CONFIG_SERVICE_ALLOWLIST_REASONS", CONFIG_SERVICE_ALLOWLIST_REASONS),
        ("API_BASE_RESPONSE_IMPORT_ALLOWLIST_REASONS", API_BASE_RESPONSE_IMPORT_ALLOWLIST_REASONS),
        ("JSON_API_HTTP_EXCEPTION_ALLOWLIST_REASONS", JSON_API_HTTP_EXCEPTION_ALLOWLIST_REASONS),
        ("MEDIA_INFO_FULL_ALLOWLIST_REASONS", MEDIA_INFO_FULL_ALLOWLIST_REASONS),
        ("MEDIA_REFRESH_ALLOWLIST_REASONS", MEDIA_REFRESH_ALLOWLIST_REASONS),
        ("PROVIDER_DETAIL_READ_ALLOWLIST_REASONS", PROVIDER_DETAIL_READ_ALLOWLIST_REASONS),
        ("MEDIA_YEAR_STR_ALLOWLIST_REASONS", MEDIA_YEAR_STR_ALLOWLIST_REASONS),
        ("APPLICATION_REPOSITORY_IMPORT_ALLOWLIST_REASONS", APPLICATION_REPOSITORY_IMPORT_ALLOWLIST_REASONS),
        *[
            (f"DISALLOWED_PATTERN_ALLOWLIST_REASONS[{pattern}]", allowlist)
            for pattern, allowlist in DISALLOWED_PATTERN_ALLOWLIST_REASONS.items()
        ],
    )
    for name, allowlist in allowlists:
        for rel, reason in allowlist.items():
            if not reason.strip():
                findings.append(Finding("scripts/check_backend_quality.py", f"{name} text {rel} text"))
            if not (REPO_ROOT / rel).exists():
                findings.append(Finding("scripts/check_backend_quality.py", f"{name} text {rel} text，text"))
    return findings

BANNED_TYPE_ALIAS_PATTERNS = (
    (re.compile(r"\bJsonObject\b"), "text JsonObject"),
    (re.compile(r"\bJsonValue\b"), "text JsonValue"),
)

HTTP_API_CALL_PATTERN = re.compile(
    r"http\.(get|post|put|delete|patch)\s*\(\s*([`'\"])(/api/[^`'\"]+)\2"
)
API_ROUTE_METHODS = {"get", "post", "put", "delete", "patch"}


@dataclass
class Finding:
    path: str
    message: str


@dataclass(frozen=True)
class ApiRoute:
    method: str
    path: str


@dataclass(frozen=True)
class RouterInclude:
    target: str
    prefix: str


@dataclass
class ApiModule:
    module: str
    router_prefix: str
    imports: dict[str, str]
    routes: list[ApiRoute]
    includes: list[RouterInclude]


def repo_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def py_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def count_lines(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def check_line_limits() -> list[Finding]:
    findings: list[Finding] = []
    for path in py_files(BACKEND_ROOT / "api" / "v1"):
        rel = repo_path(path)
        lines = count_lines(path)
        if lines > API_MAX_LINES:
            findings.append(Finding(rel, f"API text {lines} text，text {API_MAX_LINES} text"))
    for path in py_files(BACKEND_ROOT / "services"):
        rel = repo_path(path)
        lines = count_lines(path)
        if lines > SERVICE_MAX_LINES:
            findings.append(Finding(rel, f"Service text {lines} text，text {SERVICE_MAX_LINES} text"))
    return findings


def check_config_service_imports() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(
        r"(from app\.services\.config_service import|import app\.services\.config_service"
        r"|from app\.services\.config\.config_service import|import app\.services\.config\.config_service)"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        if rel in allowlist_paths(CONFIG_SERVICE_ALLOWLIST_REASONS):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "text config_service，text settings_service"))
    return findings


def check_settings_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    light_pattern = re.compile(r"\bget_(services|system|auth)_config_light\b")
    removed_module_pattern = re.compile(
        r"\b(settings_startup|settings_system_support|service_source_settings|settings_file_store|directory_path_policy)\b"
    )
    internal_import_pattern = re.compile(
        r"from app\.services\.config\."
        r"(download_client_settings|indexer_client_settings|media_server_settings|directory_settings|"
        r"naming_template_settings|quality_profile_settings|filter_preset_settings|tag_settings|"
        r"settings_config_builder|settings_file_store|service_source_settings)(?:\.|\s+import\b)"
        r"|import app\.services\.config\."
        r"(download_client_settings|indexer_client_settings|media_server_settings|directory_settings|"
        r"naming_template_settings|quality_profile_settings|filter_preset_settings|tag_settings|"
        r"settings_config_builder|settings_file_store|service_source_settings)(?:\.|\b)"
    )
    schema_service_import_pattern = re.compile(r"from app\.services\.|import app\.services\.")
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if light_pattern.search(text):
            findings.append(Finding(rel, "text *_light text，text get_base_*_config"))
        if removed_module_pattern.search(text):
            findings.append(Finding(rel, "config text wrapper/support text，text settings_service text settings service"))
        if rel == "app/schemas/config.py" and schema_service_import_pattern.search(text):
            findings.append(Finding(rel, "text schema text service text"))
        if rel.startswith("app/services/config/"):
            continue
        if internal_import_pattern.search(text):
            findings.append(Finding(rel, "config text settings text，text settings_service text"))
    return findings


def check_indexer_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    removed_import_pattern = re.compile(
        r"(from app\.services\.integration\.indexer_service import|import app\.services\.integration\.indexer_service"
        r"|from app\.services\.integration\.indexer_site_catalog_service import|import app\.services\.integration\.indexer_site_catalog_service"
        r"|from app\.services\.integration\.indexer_site_health_service import|import app\.services\.integration\.indexer_site_health_service"
        r"|from app\.services\.integration\.indexer\.sites(?:\s+import|\.)|import app\.services\.integration\.indexer\.sites(?:\b|\.))"
    )
    domain_resource_import_pattern = re.compile(
        r"(from app\.services\.domain\.resource(?:\.|\s+import\b)|import app\.services\.domain\.resource(?:\.|\b))"
    )
    integration_dependency_pattern = re.compile(
        r"(from app\.services\.application(?:\.|\s+import\b)|import app\.services\.application(?:\.|\b)"
        r"|from app\.db(?:\.|\s+import\b)|import app\.db(?:\.|\b))"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if removed_import_pattern.search(text):
            findings.append(Finding(rel, "integration indexer text；text application.workflows.resource_search，text application.views.indexer.sites，text integration.indexer"))
        if rel.startswith("app/services/integration/indexer/") and domain_resource_import_pattern.search(text):
            findings.append(Finding(rel, "integration.indexer text domain.resource，text domain/application text"))
        if rel.startswith("app/services/integration/indexer/") and integration_dependency_pattern.search(text):
            findings.append(Finding(rel, "integration.indexer text application/db，text application.workflows.resource_search"))
    return findings


def check_integration_root_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    removed_import_pattern = re.compile(
        r"(from app\.services\.integration\.download_client import|import app\.services\.integration\.download_client"
        r"|from app\.services\.integration\.schedule_tmdb_service import|import app\.services\.integration\.schedule_tmdb_service"
        r"|from app\.services\.integration\.tmdb\.schedule import ScheduleTMDBService"
        r"|from app\.services\.integration\.tmdb\.schedule import schedule_tmdb_service"
        r"|from app\.services\.integration\.danmu\.formatters(?:\s+import|\.)|import app\.services\.integration\.danmu\.formatters(?:\b|\.))"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if removed_import_pattern.search(text):
            findings.append(Finding(rel, "integration text；text integration.download.client，TMDB text tmdb_schedule_gateway，text application.workflows.danmu.formatters"))
    for path in (BACKEND_ROOT / "app/services/integration").glob("*.py"):
        if path.name == "__init__.py":
            continue
        findings.append(Finding(repo_path(path), "integration text service text，text"))
    return findings


def check_media_server_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    removed_import_pattern = re.compile(
        r"(from app\.services\.integration\.media_server_sync(?:\.|\s+import\b)|import app\.services\.integration\.media_server_sync(?:\.|\b)"
        r"|from app\.services\.integration\.media_server_sync_service import|import app\.services\.integration\.media_server_sync_service"
        r"|from app\.schemas\.integration\.media_server_sync import|import app\.schemas\.integration\.media_server_sync)"
    )
    integration_dependency_pattern = re.compile(
        r"(from app\.services\.(domain|application|config|platform)(?:\.|\s+import\b)"
        r"|import app\.services\.(domain|application|config|platform)(?:\.|\b)"
        r"|from app\.db(?:\.|\s+import\b)|import app\.db(?:\.|\b))"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if removed_import_pattern.search(text):
            findings.append(Finding(rel, "media_server_sync text integration text；text application.workflows.media_server_sync，text schemas.domain.media_server_sync"))
        if rel.startswith("app/services/integration/media_server/") and integration_dependency_pattern.search(text):
            findings.append(Finding(rel, "integration.media_server text，text domain/application/config/platform/db"))
    return findings


def check_application_command_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    old_import_pattern = re.compile(
        r"(from app\.services\.application\.(command|command_service|profile_refresh_command_service|scheduled_transfer_command_service|command_handlers|command_handlers_[a-z_]+|command_handler|command_handler_[a-z_]+|command_target_labels)(?:\s+import|\.)"
        r"|import app\.services\.application\.(command|command_service|profile_refresh_command_service|scheduled_transfer_command_service|command_handlers|command_handlers_[a-z_]+|command_handler|command_handler_[a-z_]+|command_target_labels)(?:\b|\.))"
    )
    banned_root_name_pattern = re.compile(r"^(command_.*|.*_command_service)\.py$")
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if old_import_pattern.search(text):
            findings.append(Finding(rel, "command text application.commands / application.workflows.profile_refresh / application.workflows.scheduled_transfer，text"))
        if rel.startswith("app/services/application/commands/"):
            continue
        if rel.startswith("app/services/application/"):
            name = path.name
            if banned_root_name_pattern.match(name):
                findings.append(Finding(rel, "command text application text，text application.commands text workflow"))
    return findings


def check_application_media_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    old_import_pattern = re.compile(
        r"(from app\.services\.application\.(media|media_detail|media_detail_overview|media_management|media_profile_refresh|media_server_sync)(?:\s+import|\.)"
        r"|import app\.services\.application\.(media|media_detail|media_detail_overview|media_management|media_profile_refresh|media_server_sync)(?:\b|\.))"
    )
    banned_root_name_pattern = re.compile(r"^media_.*")
    lower_layer_import_pattern = re.compile(r"(from app\.services\.application(?:\s+import|\.)|import app\.services\.application(?:\b|\.))")
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if old_import_pattern.search(text):
            findings.append(Finding(rel, "media application text；text application.views.*，text application.workflows.*"))
        if (rel.startswith("app/services/domain/") or rel.startswith("app/services/integration/")) and lower_layer_import_pattern.search(text):
            findings.append(Finding(rel, "domain/integration text application；text application text"))
        if rel.startswith("app/services/application/") and banned_root_name_pattern.match(path.name):
            findings.append(Finding(rel, "media application use case text application text，text application.views text application.workflows"))
    return findings


def check_application_package_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    allowed_packages = {"commands", "events", "views", "workflows"}
    removed_import_pattern = re.compile(
        r"(from app\.services\.application\."
        r"(addons|calendar_airings|event_consumer_service|event_dispatch_service|resource_list_service|task_view|library|indexer|danmu|discover|follow_reminder|notifications|resource_search|scheduled_transfer|subscription)"
        r"(?:\s+import|\.)"
        r"|import app\.services\.application\."
        r"(addons|calendar_airings|event_consumer_service|event_dispatch_service|resource_list_service|task_view|library|indexer|danmu|discover|follow_reminder|notifications|resource_search|scheduled_transfer|subscription)"
        r"(?:\b|\.))"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if removed_import_pattern.search(text):
            findings.append(Finding(rel, "application text；text application.views / workflows / commands / events，addon registry text app.addons.registry"))
    application_root = BACKEND_ROOT / "services" / "application"
    for path in application_root.iterdir():
        if path.name == "__init__.py" or path.name == "__pycache__":
            continue
        if path.is_file():
            findings.append(Finding(repo_path(path), "application text service/use-case text"))
            continue
        if path.is_dir() and path.name not in allowed_packages and list(path.glob("*.py")):
            findings.append(Finding(repo_path(path), "application text commands/events/views/workflows"))
    return findings


def check_application_client_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    banned_import_pattern = re.compile(
        r"(from app\.clients(?:\.|\s+import\b)|import app\.clients(?:\.|\b)"
        r"|import aiohttp\b|import httpx\b|import requests\b"
        r"|from aiohttp(?:\.|\s+import\b)|from httpx(?:\.|\s+import\b)|from requests(?:\.|\s+import\b))"
    )
    banned_client_type_pattern = re.compile(r"\b(IndexerClient|TMDBClient)\b")
    for path in py_files(BACKEND_ROOT / "services" / "application"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if banned_import_pattern.search(text):
            findings.append(Finding(rel, "application text app.clients text HTTP client；text integration text"))
        if banned_client_type_pattern.search(text):
            findings.append(Finding(rel, "application text client text；text integration text DTO/text"))
    return findings


def check_api_client_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    banned_pattern = re.compile(
        r"(from app\.clients(?:\.|\s+import\b)|import app\.clients(?:\.|\b)"
        r"|\bClientFactory\b|\bClientType\b"
        r"|\.create_client_with_config\s*\(|\.get_client_with_config\s*\(|\.get_download_client\s*\("
        r"|\.test_connection\s*\()"
    )
    for path in py_files(BACKEND_ROOT / "api"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if banned_pattern.search(text):
            findings.append(Finding(rel, "API text client/factory text；text integration/config/domain facade"))
    return findings


def check_application_repository_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    banned_pattern = re.compile(r"(from app\.db\.repositories(?:\.|\s+import\b)|import app\.db\.repositories(?:\.|\b))")
    allowlist = allowlist_paths(APPLICATION_REPOSITORY_IMPORT_ALLOWLIST_REASONS)
    for path in py_files(BACKEND_ROOT / "services" / "application"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if banned_pattern.search(text) and rel not in allowlist:
            findings.append(Finding(rel, "application text repository text；text domain/config/runtime allowlist"))
    return findings


def check_domain_application_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    application_import_pattern = re.compile(r"(from app\.services\.application(?:\s+import|\.)|import app\.services\.application(?:\b|\.))")
    for path in py_files(BACKEND_ROOT / "services" / "domain"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if application_import_pattern.search(text):
            findings.append(Finding(rel, "domain text application text；text application"))
    return findings


def check_media_server_sync_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    removed_module_pattern = re.compile(
        r"app\.services\.application\.workflows\.media_server_sync\."
        r"(event_handler|images|input_builder|metadata|need_detector|nfo_support|path_policy|refresh|runtime|server_config|server_resolver|state_tracker|sync)"
        r"(?:\b|\.)"
    )
    allowed_modules = {
        "__init__.py",
        "config.py",
        "artifacts.py",
        "needs.py",
        "nfo_plan.py",
        "pipeline.py",
        "season_runner.py",
        "service.py",
        "state.py",
        "target.py",
    }
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if removed_module_pattern.search(text):
            findings.append(Finding(rel, "server_sync text service/pipeline/target/state/config/nfo，text helper text"))
        if rel.startswith("app/services/application/workflows/media_server_sync/") and path.name not in allowed_modules:
            findings.append(Finding(rel, "server_sync text service/pipeline/target/state/config/nfo text"))
    return findings


def check_top_level_imports() -> list[Finding]:
    findings: list[Finding] = []
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        seen_non_import = False
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if seen_non_import:
                    findings.append(Finding(rel, f"text {node.lineno} text"))
                    break
                continue
            seen_non_import = True
    return findings


def check_api_repository_imports() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"from app\.db\.repositories\.|import app\.db\.repositories\.")
    for path in py_files(BACKEND_ROOT / "api" / "v1"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "API text repository，text service"))
    return findings


def check_api_base_response_imports() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"from app\.schemas\.responses\.base_responses import BaseResponse")
    for path in py_files(BACKEND_ROOT / "api"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if pattern.search(text) and rel not in allowlist_paths(API_BASE_RESPONSE_IMPORT_ALLOWLIST_REASONS):
            findings.append(Finding(rel, "API text BaseResponse text，route text BaseResponse"))
    return findings


def check_json_api_http_exceptions() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "api" / "v1") + [BACKEND_ROOT / "api" / "deps.py"]
    for path in target_files:
        rel = repo_path(path)
        if rel in allowlist_paths(JSON_API_HTTP_EXCEPTION_ALLOWLIST_REASONS):
            continue
        text = path.read_text(encoding="utf-8")
        if "HTTPException" in text:
            findings.append(Finding(rel, "text JSON API route text HTTPException，text AppException"))
    return findings


def check_exception_message_keys() -> list[Finding]:
    findings: list[Finding] = []
    target = BACKEND_ROOT / "schemas" / "exception" / "exceptions.py"
    tree = ast.parse(target.read_text(encoding="utf-8"))
    rel = repo_path(target)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_app_exception_init_call(node):
            continue

        keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg}
        if "message_key" in keyword_names:
            continue

        message_node = _exception_init_message_node(node)
        if message_node is None:
            continue
        if _is_static_message_node(message_node):
            findings.append(Finding(rel, "text AppException message text message_key"))

    return findings


def check_structured_runtime_messages() -> list[Finding]:
    findings: list[Finding] = []
    target_roots = [
        BACKEND_ROOT / "api",
        BACKEND_ROOT / "core",
        BACKEND_ROOT / "services",
        BACKEND_ROOT / "schemas" / "exception",
    ]
    runtime_models = {"CommandRecord", "ActionRecord", "EventCreate", "MediaEventCreate", "Event"}
    for root in target_roots:
        for path in py_files(root):
            rel = repo_path(path)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name_for_quality(node.func)
                if name == "ConfigurationException":
                    if any(keyword.arg == "message" for keyword in node.keywords):
                        findings.append(Finding(rel, "ConfigurationException text key-first，text message= fallback"))
                    if node.args and _contains_cjk_literal(node.args[0]):
                        findings.append(Finding(rel, "ConfigurationException text message_key，text message"))
                if name in runtime_models:
                    for keyword in node.keywords:
                        if keyword.arg == "message":
                            findings.append(Finding(rel, f"{name} text message，text message_key/message_params"))
    return findings


def check_api_message_contract() -> list[Finding]:
    findings: list[Finding] = []
    for path in py_files(API_V1_ROOT):
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and type(node.target) is ast.Name and node.target.id == "message":
                findings.append(Finding(rel, "JSON API text message text，text message_key/params"))
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "message":
                        findings.append(Finding(rel, "JSON API text message=，text message_key/params"))
    return findings


def _call_name_for_quality(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _contains_cjk_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(re.search(r"[\N{CJK UNIFIED IDEOGRAPH-4E00}-\N{CJK UNIFIED IDEOGRAPH-9FFF}]", node.value))
    if isinstance(node, ast.JoinedStr):
        return any(_contains_cjk_literal(value) for value in node.values)
    return False


def _is_app_exception_init_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "__init__":
        if isinstance(func.value, ast.Name) and func.value.id in {"AppException", "super"}:
            return True
        if isinstance(func.value, ast.Call) and isinstance(func.value.func, ast.Name) and func.value.func.id == "super":
            return True
    return False


def _exception_init_message_node(node: ast.Call) -> ast.AST | None:
    for keyword in node.keywords:
        if keyword.arg == "message":
            return keyword.value
    if len(node.args) >= 2:
        return node.args[1]
    return None


def _is_static_message_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    return False


def check_api_info_logs() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"logger\.info\(")
    for path in py_files(BACKEND_ROOT / "api" / "v1"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "API route text info text"))
    return findings


def check_disallowed_log_messages() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for path in target_files:
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        for pattern, message in DISALLOWED_LOG_MESSAGE_PATTERNS:
            if pattern.search(text):
                findings.append(Finding(rel, message))
    return findings


def check_service_dto_imports() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"from app\.schemas\.dtos\.|import app\.schemas\.dtos\.")
    for path in py_files(BACKEND_ROOT / "services"):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "Service text schemas.dtos，text domain model text service input model"))
    return findings


def check_media_info_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"\bmedia_service\.info\(")
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for path in target_files:
        rel = repo_path(path)
        if rel in allowlist_paths(MEDIA_INFO_FULL_ALLOWLIST_REASONS):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(
                Finding(
                    rel,
                    "text media_service.info()；text managed profile text simple_info，text full-detail text",
                )
            )
    return findings


def check_media_refresh_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"\bmedia_service\.(refresh_profile|refresh_profile_safely|refresh_schedule_snapshot)\(")
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for path in target_files:
        rel = repo_path(path)
        if rel in allowlist_paths(MEDIA_REFRESH_ALLOWLIST_REASONS):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "text,text"))
    return findings


def check_provider_detail_read_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"\bprovider_service\.(info|info_from_source|simple_info)\(")
    for path in py_files(BACKEND_ROOT / "services"):
        rel = repo_path(path)
        if rel in allowlist_paths(PROVIDER_DETAIL_READ_ALLOWLIST_REASONS):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "text provider text，text detail/profile refresh text"))
    return findings


def check_media_package_facade_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(
        r"from app\.services\.domain\.media\.(profile|provider|schedule)(?:\.|\s+import\b)"
        r"|import app\.services\.domain\.media\.(profile|provider|schedule)(?:\.|\b)"
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        if rel.startswith("app/services/domain/media/"):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            findings.append(Finding(rel, "media text profile/provider/schedule text，text media_service facade"))
    return findings


def check_nested_functions() -> list[Finding]:
    findings: list[Finding] = []
    for path in py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1"):
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        findings.append(Finding(rel, f"text {node.name} text {child.name}"))
    return findings


def check_disallowed_patterns() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for pattern in DISALLOWED_PATTERNS:
        for path in target_files:
            rel = repo_path(path)
            if rel in allowlist_paths(DISALLOWED_PATTERN_ALLOWLIST_REASONS.get(pattern, {})):
                continue
            count = count_pattern_occurrences(pattern, path)
            if count:
                findings.append(Finding(rel, f"text `{pattern}`，text {count} text"))
    return findings


def count_pattern_occurrences(pattern: str, path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(re.compile(pattern).findall(text))


def check_get_call_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for path in target_files:
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        allowed_mapping_names = collect_explicit_mapping_names(tree)
        for node in ast.walk(tree):
            if not is_get_call(node):
                continue
            receiver = node.func.value
            if is_allowed_get_receiver(receiver, allowed_mapping_names):
                continue
            findings.append(
                Finding(
                    rel,
                    f"text {node.lineno} text `.get()` text；text，text mapping text",
                )
            )
    return findings


def is_get_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    )


def collect_explicit_mapping_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if annotation_is_mapping(node.annotation):
                names.add(node.target.id)
        elif isinstance(node, ast.Assign) and value_is_mapping(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def annotation_is_mapping(annotation: ast.AST) -> bool:
    text = ast.unparse(annotation)
    return bool(re.search(r"\b(dict|Dict|Mapping|MutableMapping|defaultdict|DefaultDict|Counter)\b", text))


def value_is_mapping(value: ast.AST) -> bool:
    if isinstance(value, (ast.Dict, ast.DictComp)):
        return True
    if isinstance(value, ast.Call):
        name = call_name(value.func)
        return name in {"dict", "defaultdict", "Counter"}
    return False


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def is_allowed_get_receiver(receiver: ast.AST, mapping_names: set[str]) -> bool:
    if isinstance(receiver, ast.Name):
        return (
            receiver.id in mapping_names
            or name_looks_like_mapping(receiver.id)
            or receiver.id in {"router", "client", "headers", "cookies"}
        )
    if isinstance(receiver, ast.Dict):
        return True
    if isinstance(receiver, ast.Attribute):
        return attribute_get_is_protocol_mapping(receiver)
    return False


def name_looks_like_mapping(name: str) -> bool:
    return (
        name.endswith("_map")
        or name.endswith("_maps")
        or name.endswith("_dict")
        or name.endswith("_lookup")
        or name.endswith("_index")
        or "_by_" in name
    )


def attribute_get_is_protocol_mapping(receiver: ast.Attribute) -> bool:
    text = ast.unparse(receiver)
    return text.endswith((".headers", ".cookies", ".query_params", ".path_params", ".environ"))


def check_media_id_contracts() -> list[Finding]:
    findings: list[Finding] = []
    union_pattern = re.compile(r"Union\[\s*(?:str\s*,\s*MediaID|MediaID\s*,\s*str)\s*\]")
    four_segment_tv_pattern = re.compile(r"tmdb:tv:\{?[^\\s'\"}:]+\}?:\{?[^\\s'\"}]+\}?")
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        if union_pattern.search(text):
            findings.append(Finding(rel, "text Union[str, MediaID]，MediaID text"))
        if four_segment_tv_pattern.search(text):
            findings.append(Finding(rel, "text TV media_id；text season_number"))
    return findings


def check_dynamic_type_annotations() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1")
    for path in target_files:
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg is not None:
                args.append(node.args.vararg)
            if node.args.kwarg is not None:
                args.append(node.args.kwarg)
            for arg in args:
                if arg.annotation is None:
                    continue
                annotation = ast.unparse(arg.annotation)
                if _is_disallowed_dynamic_annotation_text(annotation):
                    count += 1
            if node.returns is not None:
                annotation = ast.unparse(node.returns)
                if _is_disallowed_dynamic_annotation_text(annotation):
                    count += 1
        if count:
            findings.append(Finding(rel, f"text `dict/Dict/Any` text {count} text"))
    return findings


def _is_disallowed_dynamic_annotation_text(annotation: str) -> bool:
    text = annotation.strip()
    if "Any" in text:
        return True
    if text == "dict" or text == "Dict":
        return True
    if re.search(r"\b(?:dict|Dict)\s*\[[^\]]*\b(?:Any|object)\b[^\]]*\]", text):
        return True
    return False


def check_banned_json_aliases() -> list[Finding]:
    findings: list[Finding] = []
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        for pattern, message in BANNED_TYPE_ALIAS_PATTERNS:
            if pattern.search(text):
                findings.append(Finding(rel, message))
    return findings


def _annotation_is_none(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant) and node.value is None
    ) or (
        isinstance(node, ast.Name) and node.id == "None"
    )


def _is_disallowed_union(annotation: ast.AST) -> bool:
    if not isinstance(annotation, ast.BinOp) or not isinstance(annotation.op, ast.BitOr):
        return False

    parts: list[ast.AST] = []

    def _flatten(node: ast.AST) -> None:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            _flatten(node.left)
            _flatten(node.right)
            return
        parts.append(node)

    _flatten(annotation)
    return not (len(parts) == 2 and any(_annotation_is_none(part) for part in parts))


def check_disallowed_union_annotations() -> list[Finding]:
    findings: list[Finding] = []
    target_files = py_files(BACKEND_ROOT / "services") + py_files(BACKEND_ROOT / "api" / "v1") + py_files(BACKEND_ROOT / "clients")
    for path in target_files:
        rel = repo_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and node.annotation is not None and _is_disallowed_union(node.annotation):
                count += 1
            elif isinstance(node, ast.arg) and node.annotation is not None and _is_disallowed_union(node.annotation):
                count += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None and _is_disallowed_union(node.returns):
                count += 1
        if count:
            findings.append(Finding(rel, f"text `T | None` text {count} text"))
    return findings


def check_media_metadata_contracts() -> list[Finding]:
    findings: list[Finding] = []
    disallowed_patterns = (
        (re.compile(r"\bmedia_title\s*=\s*\"\""), "text media_title text"),
        (re.compile(r"\bmedia_year\s*=\s*0\b"), "text 0 text media_year text"),
        (re.compile(r"title\s*=\s*profile\.title\s+or\s+str\(media_id\)"), "text str(media_id) text fallback"),
        (re.compile(r"\byear\s*:\s*int\s*\|\s*str\s*\|\s*None\b"), "text year text int | str | None"),
        (re.compile(r"\byear\s*:\s*str\s*\|\s*None\b"), "text year text str | None"),
    )
    for path in py_files(BACKEND_ROOT):
        rel = repo_path(path)
        text = path.read_text(encoding="utf-8")
        for pattern, message in disallowed_patterns:
            if pattern.pattern.startswith(r"\byear") and rel in allowlist_paths(MEDIA_YEAR_STR_ALLOWLIST_REASONS):
                continue
            if pattern.search(text):
                findings.append(Finding(rel, message))
    return findings


def check_frontend_api_paths_against_backend_routes() -> list[Finding]:
    findings: list[Finding] = []
    if not FRONTEND_API_ROOT.exists():
        return findings

    operations = collect_backend_api_operations()

    for path in sorted(FRONTEND_API_ROOT.glob("*.js")):
        rel = f"frontend/src/api/{path.name}"
        text = path.read_text(encoding="utf-8")
        for match in HTTP_API_CALL_PATTERN.finditer(text):
            method = match.group(1).lower()
            frontend_path = _normalize_frontend_api_path(match.group(3))
            backend_path = _find_matching_backend_path(frontend_path, operations)
            if backend_path is None:
                findings.append(Finding(rel, f"text API text `{frontend_path}` text"))
                continue
            if method not in operations[backend_path]:
                findings.append(Finding(rel, f"text API `{method.upper()} {frontend_path}` text route method text"))
    return findings


def collect_backend_api_operations() -> dict[str, set[str]]:
    modules = {
        module_name_from_api_path(path): parse_api_module(path)
        for path in py_files(API_V1_ROOT)
    }
    operations: dict[str, set[str]] = {}
    _collect_module_operations("app.api.v1.api", "", modules, operations, set())
    return operations


def module_name_from_api_path(path: Path) -> str:
    rel = path.relative_to(API_V1_ROOT).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("app", "api", "v1", *parts))


def parse_api_module(path: Path) -> ApiModule:
    module = module_name_from_api_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=repo_path(path))
    imports = collect_api_imports(tree, module)
    router_prefix = ""
    routes: list[ApiRoute] = []
    includes: list[RouterInclude] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_apirouter_call(node.value):
            prefix = _call_keyword_string(node.value, "prefix")
            if prefix is not None:
                router_prefix = prefix
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            routes.extend(_decorated_api_routes(node))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
            include = _parse_router_include(node, imports)
            if include is not None:
                includes.append(include)

    return ApiModule(module=module, router_prefix=router_prefix, imports=imports, routes=routes, includes=includes)


def collect_api_imports(tree: ast.AST, current_module: str) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source_module = _resolve_import_from_module(node, current_module)
            if source_module is None:
                continue
            for alias in node.names:
                local_name = alias.asname or alias.name
                if alias.name == "router":
                    imports[local_name] = source_module
                else:
                    imports[local_name] = f"{source_module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                imports[local_name] = alias.name
    return imports


def _resolve_import_from_module(node: ast.ImportFrom, current_module: str) -> str | None:
    if node.module is None:
        return None
    if node.level == 0:
        return node.module
    current_parts = current_module.split(".")
    package_parts = current_parts[:-1]
    base_parts = package_parts[: len(package_parts) - node.level + 1]
    return ".".join((*base_parts, node.module))


def _is_apirouter_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return call_name(node.func) == "APIRouter"


def _call_keyword_string(node: ast.Call, keyword_name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == keyword_name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _decorated_api_routes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ApiRoute]:
    routes: list[ApiRoute] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.lower()
        if method not in API_ROUTE_METHODS:
            continue
        path_value = ""
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
            path_value = decorator.args[0].value
        routes.append(ApiRoute(method=method, path=path_value))
    return routes


def _parse_router_include(node: ast.Call, imports: dict[str, str]) -> RouterInclude | None:
    if not node.args:
        return None
    target = _resolve_include_target(node.args[0], imports)
    if target is None:
        return None
    return RouterInclude(target=target, prefix=_call_keyword_string(node, "prefix") or "")


def _resolve_include_target(node: ast.AST, imports: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return imports.get(node.id)
    if isinstance(node, ast.Attribute) and node.attr == "router":
        if isinstance(node.value, ast.Name):
            return imports.get(node.value.id)
    return None


def _collect_module_operations(
    module_name: str,
    mounted_prefix: str,
    modules: dict[str, ApiModule],
    operations: dict[str, set[str]],
    stack: set[str],
) -> None:
    module = modules.get(module_name)
    if module is None or module_name in stack:
        return

    base_path = _join_api_paths(mounted_prefix, module.router_prefix)
    for route in module.routes:
        path = _canonical_api_path(_join_api_paths(base_path, route.path))
        operations.setdefault(path, set()).add(route.method)

    next_stack = {*stack, module_name}
    for include in module.includes:
        _collect_module_operations(
            include.target,
            _join_api_paths(base_path, include.prefix),
            modules,
            operations,
            next_stack,
        )


def _join_api_paths(*parts: str) -> str:
    joined = "/".join(part.strip("/") for part in parts if part != "")
    return f"/{joined}" if joined else ""


def _normalize_frontend_api_path(path_value: str) -> str:
    return _canonical_api_path(re.sub(r"\$\{[^}]+\}", "{param}", path_value))


def _canonical_api_path(path: str) -> str:
    canonical = "/" + path.strip("/")
    return canonical if canonical != "/" else "/"


def _find_matching_backend_path(frontend_path: str, operations: dict[str, set[str]]) -> str | None:
    if frontend_path in operations:
        return frontend_path
    frontend_parts = frontend_path.strip("/").split("/")
    for backend_path in operations:
        backend_parts = backend_path.strip("/").split("/")
        if len(frontend_parts) != len(backend_parts):
            continue
        if all(_api_path_segment_matches(frontend, backend) for frontend, backend in zip(frontend_parts, backend_parts, strict=True)):
            return backend_path
    return None


def _api_path_segment_matches(frontend_segment: str, openapi_segment: str) -> bool:
    if frontend_segment.startswith("{") and frontend_segment.endswith("}"):
        return openapi_segment.startswith("{") and openapi_segment.endswith("}")
    return frontend_segment == openapi_segment


def main() -> int:
    checks = [
        check_allowlist_integrity,
        check_line_limits,
        check_config_service_imports,
        check_settings_boundaries,
        check_integration_root_boundaries,
        check_indexer_boundaries,
        check_media_server_boundaries,
        check_application_package_boundaries,
        check_application_client_boundaries,
        check_api_client_boundaries,
        check_application_repository_boundaries,
        check_application_command_boundaries,
        check_application_media_boundaries,
        check_domain_application_boundaries,
        check_media_server_sync_boundaries,
        check_top_level_imports,
        check_api_repository_imports,
        check_api_base_response_imports,
        check_json_api_http_exceptions,
        check_exception_message_keys,
        check_structured_runtime_messages,
        check_api_message_contract,
        check_api_info_logs,
        check_disallowed_log_messages,
        check_service_dto_imports,
        check_media_info_boundaries,
        check_media_refresh_boundaries,
        check_provider_detail_read_boundaries,
        check_media_package_facade_boundaries,
        check_nested_functions,
        check_media_id_contracts,
        check_media_metadata_contracts,
        check_dynamic_type_annotations,
        check_banned_json_aliases,
        check_disallowed_union_annotations,
        check_disallowed_patterns,
        check_get_call_boundaries,
        check_frontend_api_paths_against_backend_routes,
    ]
    findings: list[Finding] = []
    for check in checks:
        findings.extend(check())

    if not findings:
        print("Backend quality checks passed.")
        return 0

    print("Backend quality checks failed:")
    for finding in findings:
        print(f"- {finding.path}: {finding.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
