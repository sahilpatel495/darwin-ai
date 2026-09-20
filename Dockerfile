# syntax=docker/dockerfile:1
# One image: FastAPI serves the API and the built single-page app, on $PORT.
# Build and try it:  make smoke   (or: docker build -t verity:dev . && docker run -p 8000:8000 verity:dev)

# ---- Stage 1: build the single-page app. Node never reaches the final image. ----
FROM node:22-slim AS frontend
WORKDIR /frontend
# Same pnpm version that wrote pnpm-lock.yaml, so the install is reproducible.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate
# Manifests first: the dependency layer is rebuilt only when the lockfile changes.
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ---- Stage 2: the runtime ----
FROM python:3.12-slim AS runtime
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    WORK_DIR=/tmp/verity \
    DEMO_DATA_DIR=/app/demo_data \
    PYTHONPATH=/app/backend
WORKDIR /app

# Exactly the locked versions, without test tools. Cached until pyproject.toml or uv.lock change.
# uv (pinned to the version that wrote uv.lock) and its download cache are mounted for this one
# step only, so the finished image carries neither an installer nor a second copy of every package.
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv:0.10.10,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY backend/ backend/
COPY demo_data/ demo_data/
# The Trust Report page reads eval/report.json. It exists only after an eval run, and COPY
# fails on a missing file, so look at the build context through a mount and copy it if present.
RUN --mount=type=bind,target=/ctx \
    mkdir eval && if [ -f /ctx/eval/report.json ]; then cp /ctx/eval/report.json eval/; fi
COPY --from=frontend /frontend/dist frontend/dist

# A normal user that owns nothing under /app: a bug in the app cannot rewrite the app.
# Uploads and DuckDB spill files go to WORK_DIR under /tmp, the only place it writes.
RUN useradd --uid 1000 --create-home verity
USER 1000

EXPOSE 8000
# One worker on purpose: sessions live in this process's memory, and hosts such as Render set
# WEB_CONCURRENCY, which uvicorn would otherwise read as its worker count.
# `exec` makes uvicorn PID 1 so it receives the host's stop signal and shuts down cleanly.
# --no-access-log: the session id travels in the URL path (/api/sessions/{id}/ask) and it is the
# only credential for that session's data, so the access log would write a live secret to stdout,
# where the host keeps it. Errors and warnings still log; they carry no session id.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
