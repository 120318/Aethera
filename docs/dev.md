# Development

Aethera development is Docker-only. Do not run backend Python or frontend Node commands directly on the host.

## Start

```bash
./aethera.sh dev
```

Development Compose starts:

- `backend`: FastAPI API, workers, and scheduler
- `frontend`: Vite dev server or built preview server
- `sqlite-web`: read-only SQLite inspection

Default URLs:

- Frontend: http://localhost:8173
- Backend API: http://localhost:8001
- SQLite Web: http://localhost:8081

## Local Environment

Generate `.env` from `.env.dev.example` when `PUID`/`PGID` should match the runtime data directories:

```bash
./scripts/generate_env.sh
```

`.env` is local-only and ignored by Git. `.env.dev.example` includes development-only ports and runtime controls.

Use `AETHERA_DEV_HOT_RELOAD=1` for the normal hot-reload loop. Use `AETHERA_DEV_HOT_RELOAD=0` to keep the same mounted source and `config/` data while running backend with `AETHERA_DEV_UVICORN_WORKERS` workers and frontend from a built preview bundle.

The frontend dev container uses the host UID/GID exported by `scripts/docker_compose.sh`, while `PUID`/`PGID` control runtime data ownership.

## Persistent Data

`config/` is persistent local data. Do not use it for tests or generated fixtures.

Repository checks use temporary `AETHERA_CONFIG_ROOT` directories so they cannot modify a real local deployment.

## Checks

Run the full review gate:

```bash
./scripts/review_with_gates.sh
```

Run backend tests:

```bash
./aethera.sh test-backend
```

