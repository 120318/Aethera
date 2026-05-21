FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS python-builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential gcc libffi-dev libssl-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/
RUN python3 -m venv /opt/venv \
  && python3 -m pip install --upgrade pip setuptools wheel \
  && python3 -m pip install --no-cache-dir -r /app/requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AETHERA_FRONTEND_DIST=/app/frontend_dist
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates libglib2.0-0 ffmpeg openssh-client sshpass \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=python-builder /opt/venv /opt/venv
COPY --chown=${USER_ID}:${GROUP_ID} backend/app /app/app
COPY --chown=${USER_ID}:${GROUP_ID} backend/scripts /app/scripts
COPY --chown=${USER_ID}:${GROUP_ID} backend/alembic /app/alembic
COPY --chown=${USER_ID}:${GROUP_ID} backend/alembic.ini /app/alembic.ini
COPY --chown=${USER_ID}:${GROUP_ID} --from=frontend-builder /frontend/dist /app/frontend_dist

RUN set -eux \
  && groupadd -g ${GROUP_ID} appgroup || true \
  && id -u appuser >/dev/null 2>&1 || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/sh appuser || true

COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "app.bootstrap"]
