#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT_DIR/backend/.pytest_cache"
TEST_CONFIG_ROOT="/tmp/aethera-test-config-$(date +%s)-$$"

"$ROOT_DIR/scripts/docker_compose.sh" \
  run --rm \
  -v "$ROOT_DIR/backend/tests:/app/tests" \
  -v "$ROOT_DIR/backend/.pytest_cache:/app/.pytest_cache" \
  -v "$ROOT_DIR/backend/pytest.ini:/app/pytest.ini" \
  -v "$ROOT_DIR/backend/alembic:/app/alembic" \
  -v "$ROOT_DIR/backend/alembic.ini:/app/alembic.ini" \
  -e AETHERA_CONFIG_ROOT="$TEST_CONFIG_ROOT" \
  --entrypoint pytest \
  backend \
  "$@"
