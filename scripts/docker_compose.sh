#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILES=(-f "$ROOT_DIR/docker-compose.dev.yml")

export AETHERA_DEV_UID="${AETHERA_DEV_UID:-$(id -u)}"
export AETHERA_DEV_GID="${AETHERA_DEV_GID:-$(id -g)}"

docker_can_access() {
  docker version >/dev/null 2>&1
}

sudo_docker_can_access() {
  sudo -n docker version >/dev/null 2>&1
}

print_docker_access_error() {
  cat >&2 <<'EOF'
Docker is required for Aethera quality gates, but this process cannot access the Docker daemon.

Fix the runner environment by doing one of the following:
- preferred: run review/check gates directly as a host user that can run `docker compose`
- if the runner must be containerized, mount /var/run/docker.sock, match the socket group, and do not enable no-new-privileges/seccomp rules that block socket connect
- make passwordless sudo available for docker, so this wrapper can use `sudo -n docker`

Diagnostic commands:
  id
  ls -l /var/run/docker.sock
  docker version
EOF
  {
    echo
    echo "Observed diagnostics:"
    echo "$ id"
    id
    echo "$ ls -l /var/run/docker.sock"
    ls -l /var/run/docker.sock 2>&1 || true
    echo "$ docker version"
    docker version 2>&1 || true
    if command -v sudo >/dev/null 2>&1; then
      echo "$ sudo -n docker version"
      sudo -n docker version 2>&1 || true
    fi
    if [ -r /proc/self/status ]; then
      echo "$ grep -E 'NoNewPrivs|Seccomp|CapEff|CapBnd' /proc/self/status"
      grep -E 'NoNewPrivs|Seccomp|CapEff|CapBnd' /proc/self/status || true
    fi
  } >&2
}

if docker_can_access; then
  exec docker compose "${COMPOSE_FILES[@]}" "$@"
fi

if command -v sudo >/dev/null 2>&1 && sudo_docker_can_access; then
  exec sudo -n docker compose "${COMPOSE_FILES[@]}" "$@"
fi

print_docker_access_error
exit 126
