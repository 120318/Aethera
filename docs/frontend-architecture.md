# Frontend Architecture

This document describes frontend placement rules and responsibility boundaries. Long-lived constraints are in [frontend-contracts.md](./frontend-contracts.md).

## 1. Stack

The frontend uses:

- Vue 3
- PrimeVue 4
- Tailwind v4
- Pinia stores
- composables for shared orchestration and complex state

New components and major refactors use `<script setup>`.

## 2. Source Layout

- `src/api`: backend API facades only
- `src/components`: reusable view components
- `src/composables`: reusable state, polling, orchestration, and action logic
- `src/stores`: application state shared across components
- `src/i18n`: locale messages and i18n helpers
- `src/utils`: low-level utilities that do not own business orchestration
- `src/constants`: stable non-copy constants and option definitions
- `src/views` or route-level modules: page assembly and page-local coordination

Pages should assemble existing pieces. When a page starts owning polling, dedupe, API orchestration, cross-component state, or business action construction, extract that logic into a composable or store.

## 3. API Boundary

Business code calls backend endpoints through `src/api/*.js`.

Rules:

- Do not import `@/utils/http` directly from components, stores, or composables.
- Do not scatter literal `/api/...` strings outside the API facade layer.
- Keep dynamic endpoint construction local to the facade.
- API facades should return backend payloads with minimal reshaping. Business interpretation belongs in composables or stores.

The backend quality gate statically checks literal facade paths against backend routes.

## 4. Composables

Composables own reusable interaction logic:

- polling
- command/runtime tracking
- API orchestration
- media action payload construction
- modal workflow state
- derived state used by multiple components

Good composables expose stable state and explicit commands. They should not mutate unrelated stores as hidden side effects.

## 5. Stores

Stores own cross-component state:

- notification queue
- command runtime state
- user/session state
- shared media or operation state that must outlive one component

Use stores for cross-component communication. Do not use a global event bus or browser DOM events to connect Vue components.

## 6. Components

Components own rendering, local UI state, and direct user interaction.

Rules:

- Keep components small enough to scan.
- Extract repeated UI into reusable components.
- Extract non-trivial logic into composables.
- Use PrimeVue and the design system before adding custom controls.
- Use i18n keys for user-visible text.

Components should not construct incomplete media payloads, decide backend current-object semantics, or call repositories indirectly through broad API helpers.

## 6.1 Complex Page Assembly

Complex pages should be assembled as a small set of named regions. The media detail page is the reference shape:

- A top identity component for poster/title/rating/metadata.
- A summary/status component for overview, management state, and primary actions.
- A tabbed work area for local resources, tasks, search results, and logs.
- Focused dialogs for mapping, subscription, deletion, and file detail flows.

Rules:

- Page files coordinate region components and composables; they should not own list rendering, polling, search orchestration, and dialog internals all at once.
- Region components may have local structural CSS when the layout is unique to that region, for example a poster-and-metadata grid. Those classes should describe structure, not theme values.
- Shared row behavior belongs in common components. If local resources, search results, and task rows need the same mobile stacking or tag behavior, prefer updating the shared row/tag component or pattern.
- Responsive behavior belongs at the region boundary first. Use component-specific switches only when a global responsive rule would harm other pages.
- Any new global pattern must satisfy the interface rules in `frontend-contracts.md`; otherwise keep the implementation local.

## 7. Media Detail Pages

Media detail pages are work-level pages. Season context is explicit page state.

Rules:

- TV actions that operate by season require a selected season.
- Movie actions must not carry season context.
- Command/runtime status uses backend `command.target`.
- Detail loading, season switching, action submission, and mapping dialogs should be separate composable boundaries.
- The detail page is the baseline for complex-page frontend quality. Its top identity region, overview/status region, tabbed work area, and list rows should stay as separate review targets when future changes touch the page.

## 8. Styling Placement

Reusable design decisions belong in the design system. Local component CSS is for local layout mechanics only.

Rules:

- Do not add arbitrary Tailwind visual values for new design decisions.
- Do not add static inline styles in templates.
- Do not create one-off spacing, typography, radius, or color constants in page templates.
- Use neutral metadata styling for metadata and status components for real status.

## 9. I18n Placement

User-visible copy belongs in locale files.

Rules:

- Components, composables, stores, constants, and API facades must not hardcode user-visible copy.
- Static `t()` and `$t()` keys must exist in both `zh-CN` and `en-US`.
- Protocol names, brand names, field identifiers, and internal codes may remain as literals when they are not user-facing copy.
- Backend message keys and params should be rendered through frontend i18n helpers, not displayed raw.
