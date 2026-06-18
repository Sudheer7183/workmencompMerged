FROM python:3.12-slim

# ---------------------------------------------------------------------------
# System dependencies
# Base packages for PostgreSQL + WeasyPrint (Phase 5 PDF generation).
# WeasyPrint requires GTK/Pango/Cairo libraries — must be in the Docker image.
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Pin the build toolchain — keeps builds reproducible across CI and local.
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir \
    "pip==24.3.1" \
    "setuptools==75.8.2" \
    "wheel==0.45.1"

# ---------------------------------------------------------------------------
# Install project dependencies.
# pyproject.toml is copied alone first — cache-friendly layer.
# ---------------------------------------------------------------------------
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

# ---------------------------------------------------------------------------
# Copy application source (separate layer — only invalidates on code changes)
# ---------------------------------------------------------------------------
COPY . .

# ---------------------------------------------------------------------------
# Default entrypoint — overridden by docker-compose for migrations + hot-reload
# ---------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
