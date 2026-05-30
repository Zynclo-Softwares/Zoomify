# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Zoomify — production image (FastAPI + built React SPA)
#
# Multi-stage build:
#   1. frontend-builder — bun install + vite build → frontend/dist
#   2. python-builder   — uv sync into /app/.venv
#   3. runtime          — slim Python + venv + server.py + frontend/dist
#
# FastAPI serves the SPA from frontend/dist when that directory exists
# (see server.py). The Vite config always writes the bundle there.
#
# Build locally:
#   docker build -t zoomify \
#     --build-arg VITE_CLERK_PUBLISHABLE_KEY=pk_live_... \
#     .
#
# Run locally (loads .env):
#   docker run --rm --env-file .env -p 8000:8000 zoomify
#
# Deploy contract (CMD):
#   1. python -m zoomify.migrations — apply Mongo indexes when MONGODB_URI
#      is set (idempotent; fails the container if indexes cannot be created).
#   2. uvicorn server:app — API + static UI on $PORT (Railway/Fly inject PORT).
# ---------------------------------------------------------------------------

ARG PYTHON_VERSION=3.12
ARG BUN_VERSION=1.3
ARG UV_VERSION=0.5.11

# --- Stage: frontend bundle --------------------------------------------------
FROM oven/bun:${BUN_VERSION}-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./

# Baked into the JS bundle at build time (Clerk publishable key only).
ARG VITE_CLERK_PUBLISHABLE_KEY=""
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}

RUN bun run build


# --- Stage: uv binary --------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv


# --- Stage: Python venv ------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS python-builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY server.py README.md ./
RUN uv sync --frozen --no-dev


# --- Stage: runtime ----------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    AUTO_CREATE_INDEXES_ON_BOOT=false

# Grid labels use DejaVu Sans Bold (see gridder.load_font); slim base has no fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 zoomify \
    && useradd --system --uid 1001 --gid zoomify --home-dir /app --shell /usr/sbin/nologin zoomify

WORKDIR /app

COPY --from=python-builder --chown=zoomify:zoomify /app/.venv ./.venv
COPY --from=python-builder --chown=zoomify:zoomify /app/src ./src
COPY --from=python-builder --chown=zoomify:zoomify /app/server.py ./server.py
COPY --from=frontend-builder --chown=zoomify:zoomify /frontend/dist ./frontend/dist

USER zoomify

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)" \
        || exit 1

CMD ["sh", "-c", "python -m zoomify.migrations && exec uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
