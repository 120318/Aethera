#!/usr/bin/env bash

echo "Starting development environment"
echo "================================"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=("$ROOT_DIR/scripts/docker_compose.sh")

# Stop existing containers.
echo "Stopping existing containers..."
"${COMPOSE[@]}" down 2>/dev/null || true

# Start the development environment in the background.
echo "Starting development environment..."
"${COMPOSE[@]}" up --build -d

# Wait for services.
echo "Waiting for services to start..."
sleep 3

echo ""
echo "Development environment is running."
echo "Frontend: http://localhost:8173"
echo "Backend: http://localhost:8001"
echo "SQLite Web: http://localhost:8081"
echo ""
echo "Hot reload is controlled by AETHERA_DEV_HOT_RELOAD in .env."
echo "Logs:"
echo "   All services: ./scripts/docker_compose.sh logs -f"
echo "   Frontend: ./scripts/docker_compose.sh logs -f frontend"
echo "   Backend: ./scripts/docker_compose.sh logs -f backend"
echo "   SQLite Web: ./scripts/docker_compose.sh logs -f sqlite-web"
echo "Stop services: ./scripts/docker_compose.sh down"
echo ""
echo "Following logs..."
"${COMPOSE[@]}" logs -f
