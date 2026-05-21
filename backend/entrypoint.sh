#!/bin/sh
set -e

# Entrypoint to handle permissions for data directories and drop privileges.
PUID="${PUID:-$(id -u appuser 2>/dev/null || echo 1000)}"
PGID="${PGID:-$(id -g appuser 2>/dev/null || echo 1000)}"

echo "[entrypoint] appuser uid=${PUID} gid=${PGID}"

if [ "$(id -u)" = '0' ]; then
  if ! getent group "${PGID}" >/dev/null 2>&1; then
    groupadd -g "${PGID}" appgroup || true
  fi

  if id -u appuser >/dev/null 2>&1; then
    usermod -o -u "${PUID}" -g "${PGID}" appuser || true
  else
    useradd -m -u "${PUID}" -g "${PGID}" -s /bin/sh appuser || true
  fi
elif [ "$(id -u)" != "${PUID}" ]; then
  echo "[entrypoint] running as non-root uid=$(id -u), cannot switch to configured PUID=${PUID}"
fi

# Only manage ownership of critical small config/data directories
LOG_PATH="/config/logs"
CONFIG_ROOT="/config"
DB_PATH="/config/db/aethera.db"
CACHE_PATH="/config/cache"
DB_DIR="$(dirname "${DB_PATH}")"
MEDIA_ROOT="${AETHERA_MEDIA_ROOT:-/data}"
LIBRARY_PATH="${MEDIA_ROOT}/library"
DOWNLOAD_PATH="${MEDIA_ROOT}/download"

# Ensure directories exist
mkdir -p "${CONFIG_ROOT}" "${DB_DIR}" "${CACHE_PATH}" "${LOG_PATH}" "${LIBRARY_PATH}" "${DOWNLOAD_PATH}" || true

# Only attempt chown if we are root
if [ "$(id -u)" = '0' ]; then
  for path in "${CONFIG_ROOT}" "${DB_PATH}"; do
    if [ -e "${path}" ]; then
      echo "[entrypoint] ensuring owner for $path -> ${PUID}:${PGID}"
      chown "${PUID}:${PGID}" "$path" || true
    fi
  done
  for path in "${DB_DIR}" "${CACHE_PATH}" "${LOG_PATH}"; do
    if [ -e "${path}" ]; then
      echo "[entrypoint] ensuring owner for $path -> ${PUID}:${PGID}"
      chown -R "${PUID}:${PGID}" "$path" || true
    fi
  done
  for path in "${MEDIA_ROOT}" "${LIBRARY_PATH}" "${DOWNLOAD_PATH}"; do
    if [ -e "${path}" ]; then
      echo "[entrypoint] ensuring owner for $path -> ${PUID}:${PGID}"
      chown "${PUID}:${PGID}" "$path" || true
      chmod 2775 "$path" || true
    fi
  done
else
  echo "[entrypoint] running as non-root, skipping chown"
fi

run_migrations() {
  if [ "${SKIP_ALEMBIC_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] skipping alembic migrations"
    return 0
  fi

  # SQLite is the only supported runtime database. Legacy TinyDB import is not part of startup.
  echo "[entrypoint] running alembic upgrade head"
  cd /app
  alembic upgrade head
}

if [ "$(id -u)" = '0' ]; then
  if [ "${SKIP_ALEMBIC_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] skipping alembic migrations"
  else
    echo "[entrypoint] running alembic upgrade head"
    su -s /bin/sh appuser -c "cd /app && alembic upgrade head"
  fi
else
  run_migrations
fi

# If running as root, drop privileges and execute.
if [ "$(id -u)" = '0' ]; then
  echo "[entrypoint] dropping privileges to UID ${PUID}"
  # Note: "$@" correctly preserves array arguments, but su -c requires a single string.
  # For robust CMD execution as a specific user, we use su.
  exec su -s /bin/sh appuser -c "$*"
else
  # Already non-root (specified in docker-compose), just exec.
  exec "$@"
fi
