# SAR2Action — single container: FastAPI API + built React frontend on one URL (Cloud Run).

# ---- Stage 1: build the React frontend ----
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Skip the prebuild hook: it syncs public/studio from data/ with Python, and those
# verified assets are already committed.
RUN npx tsc -b && npx vite build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# rasterio's bundled GDAL needs libexpat, which python:*-slim does not ship.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies straight from pyproject.toml (better layer caching than copying the repo first).
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
 && pip install -r requirements.txt

COPY . .
COPY --from=frontend /build/dist ./frontend/dist

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Cloud Run provides $PORT (default 8080).
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
