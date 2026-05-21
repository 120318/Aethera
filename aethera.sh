#!/usr/bin/env bash

# Aethera project entry script.
# Unified entry point for development, production, logs, status, and cleanup.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_DIR="$ROOT_DIR/scripts"
DEV_COMPOSE="$ROOT_DIR/docker-compose.dev.yml"
PROD_COMPOSE="$ROOT_DIR/compose.yaml"

case "$1" in
  "dev"|"start")
    echo "Starting development environment..."
    "$SCRIPT_DIR/dev.sh"
    ;;
  "prod")
    echo "Starting production environment..."
    "$SCRIPT_DIR/prod.sh"
    ;;
  "stop")
    echo "Stopping all services..."
    docker compose -f "$DEV_COMPOSE" down 2>/dev/null || true
    docker compose --project-directory "$ROOT_DIR" -f "$PROD_COMPOSE" down 2>/dev/null || true
    ;;
  "logs"|"log")
    shift
    "$SCRIPT_DIR/logs.sh" "$@"
    ;;
  "test-backend"|"pytest-backend")
    shift
    "$SCRIPT_DIR/test_backend.sh" "$@"
    ;;
  "coverage-backend")
    shift
    "$SCRIPT_DIR/test_backend_coverage.sh" "$@"
    ;;
  "config-migrate-to-db")
    shift
    "$SCRIPT_DIR/docker_compose.sh" run --rm --entrypoint python backend scripts/migrate_config_sections_to_db.py "$@"
    ;;
  "db-baseline-stamp")
    shift
    "$SCRIPT_DIR/docker_compose.sh" run --rm --entrypoint python backend scripts/stamp_initial_baseline.py "$@"
    ;;
  "status"|"ps")
    echo "Service status:"
    docker compose --project-directory "$ROOT_DIR" -f "$PROD_COMPOSE" ps
    docker compose -f "$DEV_COMPOSE" ps
    ;;
  "restart")
    echo "Restarting services..."
    docker compose --project-directory "$ROOT_DIR" -f "$PROD_COMPOSE" restart
    docker compose -f "$DEV_COMPOSE" restart
    ;;
  "clean")
    echo "Cleaning Docker resources..."
    docker compose --project-directory "$ROOT_DIR" -f "$PROD_COMPOSE" down
    docker compose -f "$DEV_COMPOSE" down
    docker system prune -f
    ;;
  * )
    echo "Aethera - PT subscription and automatic download tool"
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  dev               Start the development environment with hot reload"
    echo "  prod              Start the production environment"
    echo "  stop              Stop all services"
    echo "  restart           Restart services"
    echo "  status|ps         Show service status"
    echo "  logs [opts]       Manage logs; see scripts/logs.sh"
    echo "  test-backend      Run backend pytest in Docker"
    echo "  coverage-backend  Run backend pytest coverage in Docker"
    echo "  config-migrate-to-db [--remove-yaml]"
    echo "                    Copy YAML config sections into SQLite and optionally remove YAML"
    echo "  db-baseline-stamp [--force] [--repair-known-prelaunch-drift]"
    echo "                    Stamp an existing equivalent DB to the initial migration"
    echo "  clean             Clean Docker resources"
    ;;
 esac
