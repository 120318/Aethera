# Contributing

Thanks for helping improve Aethera.

## Before Working

- Read [AGENTS.md](../AGENTS.md) for repo-wide rules.
- For backend changes, read [backend contracts](./backend-contracts.md) and [backend architecture](./backend-architecture.md).
- For frontend changes, read [frontend contracts](./frontend-contracts.md) and [frontend architecture](./frontend-architecture.md).

## Development Rules

- Use Docker Compose for all runtime and test commands.
- Do not commit `.env`, `config/`, media files, database files, logs, caches, or local tool state.
- Keep user-facing configuration in SQLite unless the setting is deployment-level.
- Keep development-only runtime behavior in `.env` or compose-level settings.
- AI-assisted development is allowed, including using AI to write code and prepare Issues or merge requests. All AI-assisted changes must still receive human review before they are merged.

## Quality Gates

Run the review gate before submitting a change:

```bash
./scripts/review_with_gates.sh
```

Run backend tests when changing backend behavior:

```bash
./aethera.sh test-backend
```

## Pull Requests

- Keep changes focused.
- Include documentation updates when behavior or setup changes.
- Describe user-visible behavior, migration impact, and verification steps.
