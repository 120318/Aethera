#!/usr/bin/env bash

echo "Starting production environment"
echo "================"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/compose.yaml"
COMPOSE=(docker compose --project-directory "$ROOT_DIR" -f "$COMPOSE_FILE")

# Stop existing containers.
echo "Stopping existing containers..."
"${COMPOSE[@]}" down 2>/dev/null || true

# Start production without the development override file.
echo "Pulling production images..."
"${COMPOSE[@]}" pull

echo "Starting production environment..."
"${COMPOSE[@]}" up -d

# Wait for services.
echo "Waiting for services to start..."
sleep 3

# Show service status.
echo "Checking service status..."
"${COMPOSE[@]}" ps

echo ""
echo "Production environment is running."
echo "App: http://localhost:${AETHERA_HTTP_PORT:-8173}"
echo ""
echo "Logs:"
echo "   All logs: docker compose -f compose.yaml logs -f"
echo "   Service logs: docker compose -f compose.yaml logs -f aethera"
echo "Stop services: docker compose -f compose.yaml down"
echo "Restart services: docker compose -f compose.yaml restart"
echo "App: http://localhost:${AETHERA_HTTP_PORT:-8173}"
