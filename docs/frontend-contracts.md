# Frontend Contracts

This document defines long-lived frontend constraints. It answers:

- which style, state, and interaction rules must not be broken
- what new frontend code should follow by default
- which patterns must not keep spreading

For structure and placement rules, see [frontend-architecture.md](./frontend-architecture.md).

## 1. Styling Principles

- Frontend styling is not "add a class wherever something looks off".
- The default visual language should be restrained and coherent.
- Prefer hierarchy, spacing, and structure over decorative borders, radius, and hover effects.
- Do not create a new visual constant inside a template when the design system should own it.

The frontend stack is Vue 3, PrimeVue 4, and Tailwind v4. New code should use the established design system instead of introducing page-local visual decisions.

## 2. Token Layers

Frontend styling is expressed in three layers:

1. Design decision source of truth
2. Semantic mapping layer
3. Component consumption layer

Fixed rules:

- New spacing, color, typography, radius, and size decisions first enter the design source of truth.
- Components consume semantic tokens and stable utilities.
- Tailwind arbitrary visual values are not allowed by default.
- Component-local CSS is acceptable for local layout mechanics, but not for inventing reusable visual decisions.

## 2.1 Complex Page Quality Baseline

Complex operational pages should be reviewed as complete product surfaces, not as isolated visual tweaks. The media detail page is the baseline example for this standard.

Before calling a complex page polished, verify these regions explicitly:

- Identity region: title, subtitle, primary visual, core badges, metadata tags, and edit controls.
- Status region: current state, summary text, subscription or management state, and primary actions.
- Work region: tabs, filters, pagination, list items, empty states, and loading states.
- Dialog region: form fields, action rows, responsive width, and long copy.

Fixed rules:

- PC and mobile behavior must both be intentional. Do not accept "responsive" as a claim unless each main region has a defined desktop and narrow-screen structure.
- Long titles, original titles, actor names, resource names, tags, paths, and status text must not rely on accidental clipping. Use wrapping, line clamping, or explicit overflow behavior based on the content's value.
- Action buttons must occupy real layout space. Do not use absolute positioning plus fake padding to avoid overlap.
- Repeated resource/task/search rows keep dense desktop layouts, but narrow screens may stack actions below content when horizontal compression would damage scanability.
- Page-level local CSS may define structural skeletons such as a media detail hero layout. It must use design tokens and must not introduce reusable visual constants.
- If a page-local class starts looking like a reusable utility, move it to the pattern layer or replace it with an existing utility.
- PrimeVue `:deep()` overrides are allowed only for narrow local adaptation of a third-party component. If the same override pattern appears twice, extract a wrapper component or pattern.

## 3. Spacing Rules

Spacing tokens express relationship strength:

- `inline`: tightly related inline elements
- `item`: direct children in the same small group
- `container`: padding inside a container
- `block`: separation inside one functional region
- `section`: page-level region separation

Fixed rules:

- Do not use `container` spacing as a substitute for gap.
- Do not use page-level rhythm tokens inside compact controls.
- Dense operational screens should remain scannable; spacing should clarify grouping rather than create marketing-style air.

## 4. Typography Rules

Type scale expresses hierarchy only. It does not own color or layout.

Long-lived typography classes are semantic levels, not page-private font sizes.

Fixed rules:

- Heading hierarchy must not jump randomly.
- Secondary information defaults to `text-caption text-muted`.
- Badges, pills, counters, and compact metrics use `text-tiny` or `text-small`.
- Do not invent media-domain-specific font-size classes.
- Display-scale type belongs only to true page heroes or equivalent first-screen identity moments, not compact panels or cards.

## 5. Border, Radius, And Hover Rules

### Borderless By Default

- Page layout containers
- Static information summaries
- Pure display content blocks

### Border Allowed

- Form inputs
- Functional panels that need explicit separation
- Editable or selectable areas

### Interaction Feedback Required

- Buttons
- Tabs
- Menu items
- Links
- Clickable cards

Fixed rules:

- Static content does not get hover states by default.
- Do not add shadows, borders, or rounded decoration to pure display blocks just to make them look more active.
- Cards are for repeated items, modals, and genuinely framed tools. Do not nest cards inside cards.

## 6. Meta And Status Presentation

- Common attributes, categories, source names, and metadata use neutral metadata styling.
- Only real status semantics use status components or status colors.

Fixed rules:

- Do not use status colors to create hierarchy for ordinary metadata.
- "What it is" and "how it is doing" must be presented with different semantics.
- Status labels should come from business state derivation, not from arbitrary display strings.

## 7. Resource State Semantics

Frontend resource state uses the dual-state model:

- `torrent_status`
- `media_status`

`canonical_state` is only for fine-grained download-state display. A generic `status` field must not become a new business-decision source.

Fixed rules:

- Resource display, operations, and copy are derived from the dual-state model.
- Do not add new business branches around a single display-state field.
- If a page needs a combined label, derive it in a composable/helper and keep source states intact.

## 8. Components And State Management

- New components and major refactors use `<script setup>`.
- Complex polling, API orchestration, and combined state move into composables.
- Cross-component communication goes through stores.
- Do not use a global event bus or native DOM events for cross-component communication.
- Global notifications go through `useNotificationStore`.
- Pages coordinate composables; they should not grow into use-case controllers.

## 8.1 API Facade Contract

- Frontend business code calls the backend through `src/api/*.js`.
- Pages, stores, and composables must not scatter literal `/api/...` strings.
- Literal API paths in `src/api/*.js` must exist in backend routes, and methods must match.
- When a backend route is removed, the matching frontend API facade must be removed or rewritten. Do not keep dead endpoints.
- Dynamic paths may be composed at path-segment level, for example ``/api/v1/task/${id}``. Do not pass whole endpoint strings around as business data.

## 9. Media Action Contract

- Subscription, follow, download, delete, refresh, and similar media actions must be triggered from a complete media snapshot.
- The minimum snapshot is `media: { media_id, title, year }`.
- `title` must be non-empty and `year` must be a positive integer.
- Movie `media_id` and TV `media_id` are both three-segment work identifiers.
- Season is not a frontend identity field and must not be encoded into `media_id`.
- TV detail pages require explicit season context once a canonical `media_id` is used. Routes and API calls for `/api/v1/media/detail`, `/api/v1/media/detail-page`, overview, resources, library, tasks, operations, and actions must send a positive `season_number`.
- The only frontend detail flow allowed to omit TV season is an external source jump, such as Douban source navigation, where the backend resolves the season from source title/year or cached mapping. After resolution, the frontend must sync the route/query and continue with explicit season context.
- Season-scoped TV actions such as subscription, follow, trial run, resource search, local resource, and library overview use `media_id + season_number`.
- Movie actions use work-level `media_id` only and must not carry `season_number`.
- Command runtime state must use the backend-provided top-level `command.target` to compute keys. Do not infer media or season context from payload internals.
- When building `MediaTarget`, prefer explicit `media_type`; do not parse `media_id` strings in pages and business composables.
- Browse/search source configuration affects discovery pages and search entries only. Detail pages always show canonical TMDB work details.
- Detail route state, season context, media actions, and mapping dialogs should stay in separate composable boundaries. Do not keep piling canonical navigation, season refresh, and action submission into one page controller.

Fixed rules:

- Do not use fallbacks such as `title || name` or `year ?? null` in payload construction.
- Do not keep sending loose `media_id + media_title + media_year` payloads in main chains.
- Disable actions or show an error when detail data is incomplete. Do not send half-populated requests.
- Reuse snapshot construction helpers instead of duplicating fallback logic across composables.
- Do not encode TV season into `media_id`, such as `tmdb:tv:{id}:{season}`.
- If a season is not selected for a TV detail route or action, disable the action, ask for a season, or use the external source resolution flow. Do not default canonical `media_id` calls to season one.
- Do not send `season_number=0/1` for movies.

## 10. Global Style Interface Additions

Before adding a new global style interface, answer:

1. Is this a design token, a structural skeleton, or a local implementation detail?
2. Does it serve multiple pages or a stable skeleton?
3. Does it express a design decision that existing interfaces cannot express?
4. If only one component uses it, why should it not stay local?

If any answer is unclear, do not add it to the global style layer.
