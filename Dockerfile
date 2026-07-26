# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
# Pinned uv: reproducible builds; bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Dependency layer: manifest + lockfile only, resolved strictly from the lock
# (--locked fails loudly on drift instead of silently re-resolving).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
# Then install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# CI can run the suite against the exact artifact that ships:
#   docker build --target test -t app-test . && docker run --rm app-test
FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
CMD ["uv", "run", "pytest"]

FROM base AS runtime
WORKDIR /app
RUN useradd --create-home --uid 1000 appuser
# Explicit copy list: no uv binary, no tests, no caches in the final image.
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app
COPY --from=builder --chown=appuser:appuser /app/migrations /app/migrations
COPY --from=builder --chown=appuser:appuser /app/scripts /app/scripts
COPY --from=builder --chown=appuser:appuser /app/alembic.ini /app/alembic.ini
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"]
# --proxy-headers + forwarded-allow-ips: correct client IPs behind an ingress
# (tighten the allow-list to your proxy's address in production).
# --timeout-graceful-shutdown should not exceed the platform's grace period.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} \
    --proxy-headers --forwarded-allow-ips '*' \
    --no-server-header --timeout-graceful-shutdown 20"]
