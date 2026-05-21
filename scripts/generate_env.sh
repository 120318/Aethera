#!/usr/bin/env bash
set -euo pipefail

OUT=.env
if [ -f "$OUT" ]; then
  echo ".env already exists at $(pwd)/$OUT"
  exit 0
fi

TEMPLATE=".env.dev.example"
if [ ! -f "$TEMPLATE" ]; then
  echo "$TEMPLATE not found at $(pwd)/$TEMPLATE" >&2
  exit 1
fi

UID_VAL=$(id -u)
GID_VAL=$(id -g)
cp "$TEMPLATE" "$OUT"
perl -0pi -e "s/^PUID=.*/PUID=$UID_VAL/m; s/^PGID=.*/PGID=$GID_VAL/m" "$OUT"

echo "Generated $OUT with PUID=$UID_VAL PGID=$GID_VAL"
