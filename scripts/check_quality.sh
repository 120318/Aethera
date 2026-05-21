#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=("$ROOT_DIR/scripts/docker_compose.sh")
TEST_CONFIG_ROOT="/tmp/aethera-quality-config-$(date +%s)-$$"

"${COMPOSE[@]}" run --rm \
  -v "$ROOT_DIR:/workspace:ro" \
  --entrypoint python \
  backend /workspace/scripts/check_language_tokens.py

"${COMPOSE[@]}" run --rm \
  -v "$ROOT_DIR/backend/tests:/app/tests:ro" \
  -v "$ROOT_DIR/backend/pyproject.toml:/app/pyproject.toml:ro" \
  -e RUFF_CACHE_DIR=/tmp/aethera-ruff-cache \
  --entrypoint ruff \
  backend check app scripts tests

"${COMPOSE[@]}" run --rm \
  -v "$ROOT_DIR/backend/tests:/app/tests" \
  -e AETHERA_CONFIG_ROOT="$TEST_CONFIG_ROOT" \
  --entrypoint python \
  backend -m compileall app scripts tests

"${COMPOSE[@]}" run --rm \
  -v "$ROOT_DIR/frontend/src/api:/frontend-api:ro" \
  -e AETHERA_CONFIG_ROOT="$TEST_CONFIG_ROOT" \
  -e AETHERA_FRONTEND_API_ROOT=/frontend-api \
  --entrypoint python \
  backend scripts/check_backend_quality.py

mapfile -t QUALITY_TEST_FILES < <(
  cd "$ROOT_DIR/backend" && rg -l "pytestmark\\s*=.*\\b(drift|health|aggregation)\\b|@pytest\\.mark\\.(drift|health|aggregation)" tests | sort
)

"$ROOT_DIR/aethera.sh" test-backend "${QUALITY_TEST_FILES[@]}" -m "drift or health or aggregation"

"${COMPOSE[@]}" run --rm --no-deps frontend npm run quality
