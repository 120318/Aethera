#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT_DIR/backend/.pytest_cache" "$ROOT_DIR/backend/.coverage-reports"

"$ROOT_DIR/scripts/docker_compose.sh" \
  run --rm \
  -v "$ROOT_DIR/backend/tests:/app/tests" \
  -v "$ROOT_DIR/backend/.pytest_cache:/app/.pytest_cache" \
  -v "$ROOT_DIR/backend/.coverage-reports:/app/.coverage-reports" \
  -v "$ROOT_DIR/backend/pytest.ini:/app/pytest.ini" \
  -v "$ROOT_DIR/backend/pyproject.toml:/app/pyproject.toml:ro" \
  -v "$ROOT_DIR/backend/alembic:/app/alembic" \
  -v "$ROOT_DIR/backend/alembic.ini:/app/alembic.ini" \
  -e COVERAGE_FILE=/app/.coverage-reports/.coverage \
  --entrypoint pytest \
  backend \
  --cov=app \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=xml:/app/.coverage-reports/coverage.xml \
  "$@"
