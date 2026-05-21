# Agent Entry Point

This document is the highest-priority entry point for AI agents working on this repository.

`AGENTS.md` only defines:

- reading order
- repo-wide non-negotiables
- conflict resolution

Detailed backend/frontend rules belong in:

- [`docs/backend-contracts.md`](./docs/backend-contracts.md)
- [`docs/frontend-contracts.md`](./docs/frontend-contracts.md)
- [`docs/backend-architecture.md`](./docs/backend-architecture.md)
- [`docs/frontend-architecture.md`](./docs/frontend-architecture.md)

## Required Reading Order

1. Read this file first.
2. Then read task-specific docs only when needed:
   - doc index under [`docs/index.md`](./docs/index.md)
   - backend structure under [`docs/backend-architecture.md`](./docs/backend-architecture.md)
   - backend rules under [`docs/backend-contracts.md`](./docs/backend-contracts.md)
   - frontend structure under [`docs/frontend-architecture.md`](./docs/frontend-architecture.md)
   - frontend rules under [`docs/frontend-contracts.md`](./docs/frontend-contracts.md)

## Global & Environment Principles

- Environment: strictly Docker. Never suggest running local `python main.py` or `npm start`. All tests and runs must use `docker compose` or equivalent container commands.
- Execution: hot reload should be preserved in the dev loop; only restart containers when dependency changes require it.
- Testing: no unit tests are required unless explicitly requested, but zero syntax errors is mandatory before execution.
- User-facing language: default to Simplified Chinese for explanations, summaries, reviews, and fix descriptions unless the user explicitly asks for English.
- Review workflow: for any review task, default to running `./scripts/review_with_gates.sh` in addition to code review, unless the user explicitly asks for review-only without executable checks.
- Review output normalization: if an external or platform review flow returns English findings, restate the conclusion to the user in Simplified Chinese by default.
- Review language enforcement: for all code review outputs, the final user-facing findings, severity labels, summaries, and action items must be written in Simplified Chinese by default. Do not paste English review findings directly to the user unless the user explicitly asks to keep the English original.
- Review scope during pre-launch: by default, do not treat old-data compatibility, historical migration continuity, or persisted legacy payload compatibility as review blockers unless the user explicitly requests compatibility work.

## Repo-wide Non-Negotiables

### Documentation

- Prefer extending existing docs over creating new ones.
- Structural guidance belongs in `*-architecture.md`.
- Long-term rules belong in `*-contracts.md`.
- Executable checks belong in `docs/code-quality-gates.md`.
- Deployment and operational guidance belongs in the corresponding deployment doc.
- Create a new standalone document only when the topic is long-lived, clearly independent, cannot be naturally absorbed by an existing doc, and would not fit better as code comments, UI help text, or quality gates.

### Frontend

- Stack: Vue 3 + PrimeVue 4 + Tailwind v4.
- New components and major refactors must use `<script setup>`.
- Complex logic such as polling, API orchestration, and complex state must be extracted into `src/composables/`.
- Cross-component communication must use stores, not event bus or native DOM events.
- Styling must consume the design system; do not invent new visual constants in templates.

Detailed frontend rules live in [`docs/frontend-contracts.md`](./docs/frontend-contracts.md).

### Backend

- Stack: Python 3.12 + FastAPI.
- One API route per file.
- This project is pre-launch; do not preserve internal legacy compatibility unless explicitly requested.
- Until official launch, assume old backend data and old Alembic history may be discarded before release. Do not require transitional migrations or legacy persisted-data compatibility by default.
- `MediaID` is the only internal media identifier representation.
- Backend is model-first: do not pass `dict` or `Any` across layers.
- External/protocol-shaped data must be normalized into Pydantic models early.
- Business logic must raise domain exceptions; API/global handlers translate them.

Detailed backend rules live in [`docs/backend-contracts.md`](./docs/backend-contracts.md).

## Conflict Resolution

- If lower-level docs conflict with this file, follow this file unless the user explicitly requests otherwise in the current task.
