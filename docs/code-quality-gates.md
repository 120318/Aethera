# Code Quality Gates

This document defines Aethera's executable quality gates.

The purpose of these gates is to block known forbidden patterns before merge. The project no longer maintains historical baselines: a check either passes or fails. Real boundary-adapter logic must be expressed as a narrow, explainable, long-lived allowlist with the boundary reason documented in the script or nearby code.

## Execution

Quality gates require direct access to the host Docker daemon. The preferred runner shape is a host user that can already run `docker compose`; do not run the review gate from a restricted container or sandbox.

If a containerized runner is unavoidable, it must mount `/var/run/docker.sock`, run with the socket group, and avoid security settings such as `no-new-privileges` or seccomp/AppArmor policies that block connecting to the Docker socket. When Docker access fails, `scripts/docker_compose.sh` prints the effective user, socket permissions, Docker error, sudo fallback error, and sandbox flags.

Run the full quality gate:

```bash
./scripts/check_quality.sh
```

Review tasks run:

```bash
./scripts/review_with_gates.sh
```

Configure automated reviewers to run that command directly from the host checkout as the same host user that can run `docker compose`. Do not wrap this command in a restricted reviewer container; `review_with_gates.sh` validates Docker daemon access before running the gate and prints sandbox diagnostics when the runner is misconfigured.

Backend coverage report:

```bash
./aethera.sh coverage-backend
```

Coverage currently generates a report only. It helps prioritize missing tests, but does not define a failing threshold.

`check_quality.sh` currently runs, through Docker Compose:

- backend `ruff check app scripts tests`
- backend `python -m compileall app scripts tests`
- backend custom gates in `backend/scripts/check_backend_quality.py`
- backend selected regression tests marked `drift`, `health`, or `aggregation`
- frontend `npm run quality`
- repository language checks for user-facing hardcoded text outside locale files

All execution must go through Docker Compose or the repository scripts that use it. Do not bypass the containers with host Python or Node runtimes.

## Backend Gates

Backend quality gate script:

- `backend/scripts/check_backend_quality.py`

Rules that currently fail the gate include:

- Do not depend on the old `config_service`; startup initialization and directory path validation go through the `settings_service` facade.
- Do not restore deleted thin config wrappers or support files such as `settings_startup`, `settings_system_support`, `service_source_settings`, `settings_file_store`, or `directory_path_policy`.
- Config reads must not use `*_light` naming; use `get_base_*_config`.
- `app/schemas/config.py` must not depend on the service layer.
- Code outside the config package must not directly depend on internal settings services; use `settings_service`.
- Do not depend on the old `integration.indexer_service` entrypoint. Media resource search goes through `application.workflows.resource_search`, and external indexer adapters go through `integration.indexer`.
- Do not depend on old indexer site catalog or health service entrypoints. Site catalog belongs to `integration.indexer.catalog`, indexer site health state belongs to the config indexer settings facade, and site config views belong to `application.views.indexer.sites`.
- `integration.indexer` must not depend on `domain.resource`; resource matching, merging, and season filtering stay in domain/application.
- `integration.indexer` must not depend on application or database layers; site health persistence stays behind config/settings.
- Do not add service files directly under `app/services/integration`. Downloader interfaces use `integration.download.client`, TMDB scheduling uses `integration.tmdb.schedule.tmdb_schedule_gateway`, and danmu output formatters use `application.workflows.danmu.formatters`.
- Do not depend on old media-server-sync entrypoints. Media server sync orchestration goes through `application.workflows.media_server_sync`.
- Do not depend on old `schemas.integration.media_server_sync`; use `schemas.domain.media_server_sync`.
- `integration.media_server` only wraps external media-server calls and must not depend on domain, application, config, platform, or database layers.
- The top-level `application` package only allows `commands`, `events`, `views`, and `workflows`; do not restore old mirror packages such as `application.addons`, `application.command`, `application.media`, or `application.library`.
- The command system must use `application.commands`; profile refresh and scheduled transfer use `application.workflows.profile_refresh` and `application.workflows.scheduled_transfer`.
- Do not add concrete service or use-case files directly under `app/services/application/`.
- Do not add `command_*.py`, `*_command_service.py`, or `media_*` use-case files directly under `app/services/application/`.
- Application services must not directly depend on `app.clients` or HTTP client libraries; external systems go through `integration`.
- Application services must not directly import repositories except for allowlisted application runtime state: command queue, event dispatch queue, and media-server-sync state.
- Domain and integration layers must not depend backward on application. Media command orchestration stays in application.
- Domain must not depend on application. Search, command, and download orchestration stay in application.
- `application.workflows.media_server_sync` keeps only explicit roles such as service, pipeline, target, state, config, and nfo; do not restore old helper modules.
- Nested functions are forbidden in `app/services` and `app/api/v1`.
- Non-top-level imports are forbidden in `app`.
- `Union[str, MediaID]` is forbidden.
- New `isinstance(` usage is forbidden.
- API routes must not directly depend on repositories.
- API routes must not directly create or fetch clients through `ClientFactory`, `ClientType`, or client `test_connection`; route external checks through integration/config/domain facades.
- API routes must not directly depend on `BaseResponse`.
- Standard JSON API routes must not use `HTTPException` for business errors.
- API route layers should not write business `info` logs directly.
- Service layers must not depend on `schemas.dtos`.
- Non-allowlisted chains must not call `media_service.info()` directly.
- `media_service.py` is a facade/orchestration boundary only; do not add provider aggregation, profile persistence, or schedule implementation details there.
- Do not use empty string or zero placeholders for `media_title` or `media_year`.
- Do not pass loose `media_id + media_title + media_year` through main chains.
- Do not add internal media models with `year: str | None` or `year: int | str | None`.
- Do not use `str(media_id)` as an internal title fallback.
- Do not write `season_number=0/1` into movie main chains.
- Do not hardcode `season_number=1` in search or discovery entries.
- Do not encode season into `media_id` strings and parse it back out.
- Do not add four-segment TV ids such as `tmdb:tv:{id}:{season}`.
- Do not add `object`.
- Do not add union types other than `T | None`.
- Do not add `JsonObject` or `JsonValue`.
- Do not add bare `dict`.
- Do not add `dict[str, object]` or `dict[str, Any]`.
- `.get()` is allowed only for true mapping or protocol mapping reads; fixed-field objects must not use `.get()` to avoid model contracts.
- Domain and API layers must not add dependencies on `douban_models.py` or `tmdb_models.py`.
- Ordinary domain services must not directly depend on provider clients.
- Pytest warnings are configured as errors.

Future backend gates should prioritize chain governance:

- Routes should not keep defining current-object semantics and create/update branches independently.
- Once a formal business object is loaded, the same request should not query it again by the same semantics.
- Once a complete `MediaIdentity` is known, code should not call provider/profile only to fill title or year.
- Deep methods should not query missing fields locally when upstream should pass them.
- Compensating `ensure_*` and `must_*` business methods should not be added.
- Guarantee-style methods must not hide provider/profile fallback, placeholder creation, or state repair.

## Frontend Gates

Frontend quality gate script:

- `frontend/scripts/check-quality.mjs`

Rules that currently fail the gate include:

- Components must not use `useToast` directly.
- Components must not explicitly import `defineProps` or `defineEmits`.
- DOM events must not be used for cross-component communication.
- Subscription, follow, and download action layers must not use media snapshot fallbacks such as `title || name` or `year ?? null`.
- Movie action chains must not write `season_number=0/1`.
- Frontend action chains must not encode TV season into `media_id`.
- When no TV season is selected, action code must not default to season one.
- Components and composables above the shared line-count limit must be split.
- New components with `<script>` must use `<script setup>`.
- Components and non-`src/api` layers must not import `@/utils/http` directly.
- Templates must not add static `style=""`.
- Tailwind arbitrary visual values must not be added.
- Non-locale frontend source must not add hardcoded user-visible Chinese text; user-visible copy belongs in `src/i18n/locales`.
- Static `$t()` and `t()` keys must exist in both `zh-CN` and `en-US`.
- Static English text in templates and `label`, `placeholder`, `title`, or `desc` object copy must not bypass i18n. Brand names, protocol values, and internal fields must stay in script allowlists or be represented as explicit non-copy fields.
- Frontend source under `src/api`, `src/components`, `src/composables`, `src/constants`, `src/stores`, and `src/utils` must be reachable from the static import/export graph. Unreferenced files should be deleted; true dynamic entries must be wired explicitly into the graph.

Future frontend gates should prioritize action-chain consistency:

- Media detail, media management, and dialogs should not invent different payload semantics for the same main chain.
- Media snapshots already known at action entry should not degrade into partial field combinations downstream.
- State transition semantics for the same business action should converge into shared helpers or composables instead of being repeated per page.

## Repository Language Gates

Repository-level language checks enforce the i18n boundary:

- User-facing Simplified Chinese is allowed only in locale translation files.
- Non-locale Chinese used as external protocol, provider, or parser data must be registered in `scripts/check_language_tokens.py` with token, allowed path pattern, and reason.
- Test files are excluded from repository language token checks so fixtures can model real-world media names and parser input.
- Whole-file Chinese allowlists are not allowed; the gate checks every discovered Chinese token individually.
- Backslash-u Unicode escape sequences are disallowed outside locale translation files because they hide text from normal search.
- Non-localized backend catalogs live under `backend/app/services/i18n/locales`.
- Frontend locale messages live under `frontend/src/i18n/locales`.
- Backend wire fallbacks should not return localized placeholders such as translated unknown labels; return an empty/structured value and let the presentation layer render the localized copy.

English text outside locale files is allowed only when it is not user-facing product copy, or when the user explicitly asked for English documentation/comments. User-facing frontend copy still belongs in locale files.

## Exception Rules

Exceptions are not baselines and must not hide historical debt. Before adding an exception:

- The exception must represent a clear boundary, such as a framework entrypoint, protocol conversion layer, or external format parser.
- The exception scope must be as small as possible, preferably a file or function.
- The reason must be visible in the script or nearby code.
- When the boundary disappears, the exception must be removed.

New features must not bypass gates by adding exceptions.
