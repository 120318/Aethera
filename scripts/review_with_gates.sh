#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

"$ROOT_DIR/scripts/docker_compose.sh" version >/dev/null
"$ROOT_DIR/scripts/check_quality.sh"
