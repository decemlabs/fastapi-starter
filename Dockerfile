# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Install dependencies first (cached layer) using only the manifest.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev
# Then install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

FROM base AS runtime
WORKDIR /app
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
