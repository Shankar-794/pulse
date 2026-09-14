# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    SQLITE_DB_PATH=/app/data/pulse.db

# Install curl for container healthcheck and clean apt caches
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory to project root equivalent
WORKDIR /app

# Create unprivileged system user/group and persistent data directory for SQLite
RUN groupadd -r pulse && \
    useradd -r -g pulse -d /app -s /sbin/nologin pulse && \
    mkdir -p /app/data && \
    chown -R pulse:pulse /app

# Copy dependency manifest first for optimal Docker layer caching
COPY --chown=pulse:pulse backend/requirements.txt /app/backend/requirements.txt

# Install production Python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend application source
COPY --chown=pulse:pulse backend /app/backend

# Switch to unprivileged runtime user
USER pulse

# Expose default port
EXPOSE 8000

# Native healthcheck using comprehensive system health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/system/health || exit 1

# Launch uvicorn with dynamic Render $PORT support and exec signal delegation
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
