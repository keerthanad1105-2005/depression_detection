#!/bin/sh
set -e

echo "=========================================================="
echo " MindScan Clinical Backend Starting in Production"
echo "=========================================================="

# 1. Automatic database schema migration
echo "[Startup] Executing Alembic migrations against target database..."
python -m alembic upgrade head || {
    echo "[Startup] WARNING: Alembic migration encountered an issue; continuing startup..."
}

# 2. Worker concurrency tuned for ML memory budget (PyTorch/Transformers)
# Default 1 worker avoids multi-gigabyte duplicate memory footprints on constrained containers.
WORKERS=${WEB_CONCURRENCY:-1}
PORT_NUM=${PORT:-8000}

echo "[Startup] Launching Uvicorn server on port ${PORT_NUM} with ${WORKERS} worker(s)..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT_NUM}" \
    --workers "${WORKERS}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
