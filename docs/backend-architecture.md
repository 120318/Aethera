# Backend Architecture

This document describes the current backend structure and placement rules. It answers:

- where code should live
- what each layer owns and does not own
- where to look first when adding a feature

Long-lived constraints, chain governance, and logging rules live in [backend-contracts.md](./backend-contracts.md). Executable checks live in [code-quality-gates.md](./code-quality-gates.md).

## 1. Overall Structure

The backend is organized around these boundaries:

- `app/api/v1`: HTTP boundary layer
- `app/services/application`: use-case orchestration, command bus, event dispatch and consumption
- `app/services/domain`: core business services
- `app/services/integration`: external systems and third-party protocol integration
- `app/services/platform`: cross-domain platform capabilities and runtime infrastructure
- `app/services/audit`: event, action, and audit-log chains
- `app/services/config`: configuration loading, configuration objects, and startup configuration
- `app/db/repositories`: persistence access
- `app/schemas`: API, domain, runtime, and persistence boundary models

The structure is semantic, not a mirror of HTTP endpoints. A package exists because it owns a responsibility, not because a route needs a folder with the same name.

## 2. API Layer

`app/api/v1` only owns:

- parsing path, query, and body input
- parsing string ids into `MediaID` at the boundary
- calling one use-case entrypoint
- returning inner payload models

It does not own:

- business orchestration
- current-object decisions
- direct repository reads
- human-debugging `info` logs

Rules:

- One route file carries one API action.
- Routes do not implement business state machines.
- Routes do not query again to "make sure" when the inner layer already owns the decision.
- Business exceptions are raised as domain/application exceptions and translated by global handlers.

## 3. Service Layers

### 3.1 `application/`

This layer owns use-case buses, UI read models, and cross-domain orchestration. It is grouped by application responsibility shape, not by mirrored domain nouns.

Current package meanings:

- `commands/`: command creation, queueing, execution state progression, handler registration, and assembly
- `events/`: event dispatch, consumption, and consumer matching
- `views/`: read-model aggregation for API/UI, such as calendar, task views, media detail overview, media management, resource state, library views, and indexer site views
- `workflows/`: cross-domain action orchestration, such as subscription runs, trial runs, danmu generation, notification sending, profile refresh, and media-server sync

Good fits:

- aggregation required by one API/UI read model
- orchestration for one cross-domain action
- application runtime mechanisms such as commands and events

Bad fits:

- domain-mirror packages such as `media/`, `library/`, or `resource/`
- concrete download, transfer, media, or library operation implementation
- domain concurrency control
- third-party protocol parsing
- repository details

### 3.2 `domain/`

This layer owns core business semantics and main business chains.

Typical domains:

- download
- transfer
- subscription
- media detail and search
- media management
- history
- profile

Good fits:

- the primary meaning of a complete business action
- current-object decisions
- strong/weak dependency boundaries
- state transitions

Bad fits:

- directly operating on third-party raw payloads
- passing broad dictionaries between layers
- command or event infrastructure
- UI read-model shaping

### 3.3 `integration/`

This layer connects the outside world and translates third-party protocols into repository-consumable models.

Good fits:

- indexer, torrent, and downloader client integration
- media provider and TMDB support
- media-server protocol integration
- optional third-party protocol adapters such as OIDC providers, Telegram channels, and future danmu providers

Bad fits:

- internal business orchestration
- API boundary parsing
- passing third-party payloads upward unchanged
- depending on application or domain implementation details unless the boundary explicitly allows it

### 3.4 `addons/`

`app/addons` is the optional-capability assembly layer. It only describes which optional capabilities exist, whether they are enabled, which events they subscribe to, and whether they provide scheduled tasks.

Good fits:

- `AddonDescriptor`
- addon registry
- descriptor registration for auth, notifications, future danmu, and similar optional capabilities

Bad fits:

- OIDC, Telegram, danmu provider, or other concrete integrations
- notification sending or danmu matching use-case orchestration
- business capability HTTP APIs

Boundary rules:

- Concrete third-party adapters live in `app/services/integration/<capability>/...`.
- Optional capability workflows live in `app/services/application/workflows/<capability>/...`.
- Core business semantics still live in `app/services/domain/...`.
- `/api/v1/addons` exposes only addon framework information and scheduled-task metadata. Auth, notification, danmu, and similar business APIs live under their capability routes.

### 3.5 `platform/`

This layer owns cross-domain runtime support.

Good fits:

- cache
- runtime cache
- scheduler runtime
- auth support infrastructure
- unified domain-lock infrastructure

Bad fits:

- core business semantics
- external protocol translation entrypoints
- domain strategies such as media-resource naming

### 3.6 `audit/`

This layer owns cross-cutting audit capabilities:

- events
- actions
- action logs
- audit search support

Good fits:

- event/action recording
- event/action querying
- snapshot completion for audit records
- search text generation for persisted audit views

Bad fits:

- core business result calculation
- third-party protocol adapters
- primary chain state transitions

### 3.7 `config/`

This layer is the configuration boundary:

- configuration file reads
- settings objects
- startup configuration
- bootstrap configuration assembly

Good fits:

- config files
- settings object construction
- initialization-time configuration assembly
- public config facades such as `settings_service`

Bad fits:

- core business logic
- route-level ad hoc reads of entire config objects
- exposing internal settings services outside the config package

## 4. Repository Layer

`app/db/repositories` only owns persistence.

Rules:

- Convert database rows to Pydantic models as soon as practical after reading.
- If the semantics require a single current object, the repository should provide a single-object query.
- Do not push current-object semantics upward by returning `list + sort` and making services guess.
- Repository models should describe persistence records, not UI response shapes.
- Repository code should not call domain/application workflows.

## 5. Schema Layer

`app/schemas` is the model boundary, not a miscellaneous dumping ground.

Rules:

- Request and response models belong to API boundaries.
- Service input and runtime models belong to business or orchestration boundaries.
- Persistence records belong to repository boundaries.
- `dict`, `Any`, third-party dataclasses, and raw provider models must not pierce service main chains.
- Provider raw models may exist under integration-private boundaries, but normalized models must be used before entering domain or application chains.

## 6. Common Placement Patterns

### Commands, Events, And Scheduling

- HTTP entry lives in `api`.
- Orchestration entry lives in `application`.
- Audit records live in `audit`.
- Actual business execution lives in the relevant domain or workflow.

### Core Business Main Chains

- Primary meaning lives in `domain`.
- External system protocols live in `integration`.
- Parsers, filters, caches, naming helpers, and other supporting capabilities live in their explicit support package.

### Concurrency Control

- Lock semantics are defined by the domain.
- Lock infrastructure is implemented by platform/support capabilities.
- Commands and schedulers trigger domain entries; they do not own object-level locking decisions.

### UI Read Models

- UI aggregation lives in `application/views`.
- Domain services provide stable business data, not page-shaped payloads.
- API routes return view models without rebuilding the aggregation in the route.

### Optional Capabilities

- Descriptor and enablement metadata live in `app/addons`.
- Third-party adapters live in `integration`.
- Runtime workflow lives in `application/workflows`.
- Capability-specific APIs live under their API capability routes, not under `/addons`.
