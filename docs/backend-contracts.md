# Backend Contracts

This document defines long-lived backend constraints and chain governance rules. It answers:

- which rules must not be broken
- what to inspect first when reviewing a business chain
- which patterns must not keep spreading

For the current backend structure, see [backend-architecture.md](./backend-architecture.md).

## 1. Chain Review Standard

When reviewing or refactoring any backend business chain, judge issues in this order. Do not start with low-value style cleanup:

1. Whether the primary business meaning is clear
2. Whether the input contract is narrow enough
3. Whether already-known information is being confirmed again
4. Whether calls exist only to compensate for weak upstream contracts
5. Whether the code preserves incorrect compatibility
6. Whether the chain creates intermediate dirty state
7. Whether ownership boundaries are clear
8. Whether strong and weak dependencies match the use case
9. Whether incidental side effects are mixed into the primary chain
10. Whether model layers are mixed
11. Whether runtime type dispatch is being used

Short rule:

- inspect semantics, input, dependencies, and state first
- leave style-only issues until the end
- `isinstance` is a project-level forbidden pattern, not an acceptable transition technique

Current project stage:

- Before official launch, old-data compatibility, historical Alembic continuity, and persisted legacy payload compatibility are not default blockers for backend refactors.
- Unless the user explicitly requests a compatibility plan, assume old data and old Alembic history may be cleaned before release.

## 1.1 Type Contract Rules

Backend type contracts follow these rules:

1. `T | None` may only express data that is genuinely absent.
2. Other union types must not be added.
3. `object` must not be added.
4. `Any`, `dict`, and `Mapping` must not be used as cross-layer contracts.
5. Runtime type dispatch with `isinstance` must not be used.
6. `dict` is allowed only for true mapping semantics.
7. Generic JSON carriers such as `JsonObject` or `JsonValue` must not enter formal contracts.
8. Service, domain, and API main-chain methods must not use `**kwargs` for business inputs. Use explicit named parameters or formal input models.

Fixed interpretation:

- If a field is required at entry, required during flow, and required after persistence, it must be typed as non-null.
- Do not loosen a field to `T | None` for dirty data, caller convenience, or temporary migration laziness.
- Primitive unions, model unions, and protocol unions must not be added.
- Multi-shape inputs must be normalized at the boundary, then passed inward as one formal model.
- `**kwargs` may remain in framework adapters, test doubles, and log forwarding, but not in business-chain contracts.
- Real mappings such as `dict[int, str]` or `dict[str, DownloaderConfig]` are allowed.
- Fixed-field objects must be modeled with `BaseModel`, not disguised as `dict[str, T]`.
- `model_dump()`, JSON columns, and cache reads/writes may create temporary dictionaries, but those dictionaries must not leak into service, schema, or repository contracts.

## 2. Execution Chain Rules

Backend execution chains follow these rules by default:

1. Inputs carry only fields needed for execution.
2. Information already known by the caller is passed explicitly by the caller.
3. Uniqueness, deduplication, and current-object semantics are defined by real business dimensions.
4. Historical leftover state must not participate in current-object decisions.
5. Reuse, reactivation, and compensation require semantic consistency checks first.
6. State recovery is a full semantic update, not a local patch.
7. Only explicitly allowed states may be reused.
8. Display fields and execution fields are evaluated separately.
9. Names must express real business meaning, not vague implementation details.
10. Current-object decisions must be centralized, not scattered across routes and services.
11. Already-loaded objects must not be queried again with the same semantics in the same request.
12. Already-known media snapshots must not routinely fall back to provider or profile lookups.
13. Before fixing a missing deep parameter locally, check whether upstream should pass it through.
14. One action chain has one primary meaning. Side effects must not drive the primary implementation backward.
15. Business methods named `ensure_*` or `must_*` must not carry compensation semantics.
16. Main-chain execution and profile enrichment must be separated. Do not hide both behind a guarantee-style method.

These rules apply to download, transfer, subscription, command, media, settings, and similar chains.

Fixed interpretation:

- Routes may validate boundary input, but should not define create, update, or reactivate semantics.
- If the caller already has a formal object such as `Subscription`, `TaskData`, or `ManagedMediaProfile`, downstream code must not query the same object again by id.
- If the caller already has a complete `MediaIdentity`, downstream code must not query provider or profile only to fill title or year.
- A method that says "this field is missing, so query it here" is usually a chain-design smell. Prefer correcting upstream input.
- Post actions such as event emission, notification, profile refresh, and command enqueue consume the main-chain result. They must not force meaningless queries into the main chain.
- If an `ensure_*` or `must_*` method queries provider data, creates placeholders, repairs state, or fills fields, it is a compensation box and should not spread.
- Main-chain methods consume formal input already assembled at the entry boundary. Enrichment, cache backfill, and profile refresh are independent weak-dependency chains.

## 3. Default Chain-Audit Workflow

When changing download, transfer, subscription, command, media, settings, or other main chains, use this workflow:

1. Expand the full chain: frontend entry, API, domain, downstream dependencies, and side effects.
2. Define the primary meaning.
3. Define the current object and its single uniqueness decision point.
4. Identify compensating `ensure_*`, `must_*`, and pseudo-guarantee methods.
5. Narrow input contracts.
6. Remove repeated confirmation of already-known data and meaningless calls.
7. Clarify current-object, dedupe, reuse, and reactivation semantics.
8. Remove incidental side effects and intermediate dirty state.
9. Only then handle style and quality gates.

Default deliverables:

- Provide a main-chain diagram or an equivalent chain expansion.
- List the earliest layer where each required field is already known.
- List queries that can be deleted and dependencies that must remain.
- List guarantee-style methods that actually perform compensation, and split them into main-chain execution plus post-chain enrichment.
- If these points cannot be answered, do not jump directly into patching code.

## 4. Event And Action Audit Template

Event and action audit chains follow this template:

1. Prefer top-level fields.
2. `meta` carries only the minimal snapshot.
3. Events are not domain-object transport channels.
4. Action records and events must share the same mental model.
5. Display fields must not drive heavy dependencies.
6. Strong and weak dependency boundaries must be explicit.

Fixed rules:

- Do not duplicate semantics in `meta` when a top-level field already exists.
- Use explicit Pydantic snapshot models for `meta` by default.
- Do not put full domain objects, repository records, or ORM objects into `meta`.
- Ordinary events and media events are modeled and emitted separately.
- Events with `media_id` must use the media-event entrypoint. Do not keep reusing generic `emit()`.
- A media event that carries `media_id` must also carry complete `MediaIdentity`, not fragmented fields.

## 5. Media Info Boundary Template

Media information is used in three levels: light summary, tracked profile, and full detail. Do not mix them.

Fixed rules:

- Ask what level of information the chain actually needs before selecting a dependency.
- Light display and light decisions must not pull full details.
- If a stable summary source already exists, do not call a heavier dependency only to refill display fields.
- Full detail is reserved for chains that truly need complete media semantics.

Identity rules:

- Internal main chains that represent a media object must have `MediaID + title + year`.
- `title` is a non-empty string. `year` is a positive integer.
- `MediaID` is converted to string only for serialization. Runtime internals do not mix it with strings.
- Movie `MediaID` shape is `provider:movie:id`.
- TV `MediaID` shape is `provider:tv:id`.
- Season is not part of `MediaID`.
- `MediaID` represents canonical work identity. Season-scoped TV business objects use `MediaTarget(media_id, season_number)`.
- `MediaIdentity` represents executable media identity and must include `MediaTarget + title + year`.
- Command records must persist a normalized top-level `MediaTarget` snapshot. Queries and UI state must not infer season context from command payload internals.
- TV `media_id` detail reads must carry an explicit positive `season_number`. This applies to `/api/v1/media/detail`, `/api/v1/media/detail-page`, detail overview, resource/library/task reads, operations, and other media-id based detail/action routes.
- The only detail entry allowed to omit TV `season_number` is the external source entry, such as a Douban source lookup. That path may use source title, year, cached mapping, or provider data to resolve the season, then must return/store the resolved season explicitly.
- Generic media reads such as `media_service.info()` must not implicitly fill the first season.
- Profile/cache hits must return directly. Only misses may synchronously build from source. Stale refresh is handled by explicit refresh commands or schedulers.
- `simple_info()` is profile-only lightweight reading. It must not trigger provider lookup or full detail construction.
- Execution chains must not call full detail or providers to fill `title`, `year`, `imdb`, `douban`, or `season`; missing fields mean the entry contract is wrong.
- Resource search, subscription run, download creation, transfer, and delete chains must consume formal snapshots from command payloads, subscription state, or task context.
- Provider detail reads are allowed only for detail-cache miss construction and explicit profile refresh boundaries.
- Profile refresh is allowed only through explicit refresh commands, schedulers, calendar fallback, or weak post-chain enrichment. It must not participate in current-object decisions.
- Download-task season and episode coverage must be parsed through unified `TaskEpisodeCoverage`. Resource lists, task lists, delete, transfer, and subscription completion must not each reinterpret season numbers.
- Browse/search source is controlled by global `browse_source` configuration. Switching source affects discovery and search entries only; it does not change the canonical TMDB detail contract.
- Internal canonical `MediaID` is TMDB-based. Douban ids are external aliases, browse-source hints, or search enhancement fields.
- Work-level media snapshots express only `media_id + title + year`; when entering season-scoped execution they must be upgraded to `MediaIdentity` with season context.
- Generic media information models may have optional `season_number`, but movie objects must not carry it, and any present `season_number` must be positive.
- Only TV-specific formal contracts or known season-scoped action chains require `season_number: int`.
- Season-scoped TV chains such as subscription, trial run, resource search, resource list, library overview, and similar flows must not decide current objects with work-level `media_id` alone.
- Movie execution chains must not carry `season_number`.
- Provider raw response models may be loose, but normalized business models must not keep `Optional year`, `str year`, `0`, or empty-string placeholders.
- Objects with known `media_id` but missing `title/year` must not enter subscription, event, download, or transfer main chains.
- Do not encode season inside the `media_id` string and parse it back out.
- Do not add four-segment TV ids such as `tmdb:tv:{id}:{season}`. Use explicit `season_number`.
- `douban_models.py` and `tmdb_models.py` may stay inside provider clients or explicit integration-private implementations only.
- Domain, API, and public service interfaces must not expose `Douban*` or `TMDB*` models as input or return types.
- Upstream consumers use standard models and must not branch on provider model classes.

## 6. Logging Governance Template

Backend logging follows the quiet-production model.

### `DEBUG`

- Hot-path details
- Per-resource, per-file, per-candidate, cache hit/miss, and filtering details

### `INFO`

- Process startup and shutdown
- Important business state changes
- Batch summaries
- No per-item success spam

### `WARNING`

- Weak dependency failures
- Data inconsistencies that were degraded
- External service failures when the primary chain can continue

### `ERROR` / `exception`

- The current action truly failed
- Use stack traces only at the final failure point or when the stack is required

Fixed rules:

- Route layers do not write business `INFO` by default.
- Human debugging chatter, process narration, and per-item success logs are not allowed.
- Per-item success logs should usually be `DEBUG`.
- Important `INFO` records should include stable identifiers.

## 7. JSON API Error Contract

Standard JSON APIs follow these rules:

- Route layers must not use `HTTPException` for business errors.
- Business errors raise `AppException`.
- API/global handlers translate exceptions into JSON responses.
- Error responses expose stable machine-readable keys and structured parameters.
- Human-readable messages are rendered by the frontend or by explicit server-side notification renderers.
- Backend internals must not persist localized text as the source of truth for command, task, event, or action errors.

## 8. Frontend API Contract Gate

Frontend/backend API paths must not rely on verbal convention.

Fixed rules:

- New literal `/api/...` calls in `frontend/src/api/*.js` must correspond to real backend routes under `app/api/v1`.
- Methods must match. The frontend must not keep dead calls to deleted or unimplemented backend routes.
- Backend quality gates statically parse `APIRouter(prefix=...)`, `include_router()`, and route decorators to validate frontend API facades.
- The gate checks literal paths in the API facade layer only. Pages and composables should not bypass `frontend/src/api`.
