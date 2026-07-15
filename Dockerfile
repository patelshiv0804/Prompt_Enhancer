# ==========================================
# Stage 1: Build Dependencies
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system utilities needed for building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Setup virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ==========================================
# Stage 2: Runtime Container
# ==========================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies (e.g. pg client libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application codebase
COPY app/ /app/app
COPY alembic/ /app/alembic
COPY alembic.ini /app/alembic.ini

# Set environment defaults
ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose application port
EXPOSE 8000

# Create and run under a secure non-root user
RUN useradd -u 10001 -m appuser \
    && chown -R appuser:appuser /app
USER appuser

# Healthcheck for orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Start FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
