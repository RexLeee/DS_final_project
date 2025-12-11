# ============================================
# Backend Dockerfile - Multi-stage UV Build
# Flash Sale System
# ============================================

# Build stage
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Set environment variables for UV
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project itself)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY ./src ./src
COPY ./scripts ./scripts
COPY ./alembic ./alembic
COPY ./alembic.ini ./

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================
# Production stage
FROM python:3.11-slim-bookworm AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install runtime dependencies (required for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/src ./src
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini ./

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start application with optimized settings for high concurrency (K8s best practice)
# --workers 2: Dual workers per Pod for better CPU utilization with 500m+ CPU
# --loop uvloop: 2-3x async performance improvement
# --http httptools: Faster HTTP parsing
# --timeout-keep-alive 30: Keep connections alive to reduce EOF errors
# --limit-concurrency 500: Handle 1000 VU load testing
# --limit-max-requests 10000: Prevent memory leaks by recycling workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--loop", "uvloop", "--http", "httptools", "--timeout-keep-alive", "30", "--limit-concurrency", "500", "--limit-max-requests", "10000"]
