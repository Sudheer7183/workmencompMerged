FROM python:3.12-slim

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Pin the build toolchain — keeps builds reproducible across CI and local.
# These versions are known-good with setuptools.build_meta.
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir \
    "pip==24.3.1" \
    "setuptools==75.8.2" \
    "wheel==0.45.1"

# ---------------------------------------------------------------------------
# Install project dependencies.
# pyproject.toml is copied alone first — this layer is cache-friendly and
# only re-executes when dependencies change, not on every source edit.
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