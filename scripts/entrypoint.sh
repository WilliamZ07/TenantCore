#!/usr/bin/env bash
set -eo pipefail

ROLE="${1:-web}"

if [ "$ROLE" = "web" ]; then
    echo "[entrypoint] Applying database migrations..."
    alembic upgrade head

    echo "[entrypoint] Starting Uvicorn ASGI server..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers "${WEB_CONCURRENCY:-4}" \
        --no-access-log
elif [ "$ROLE" = "worker" ]; then
    echo "[entrypoint] Starting Arq background worker..."
    exec arq app.workers.arq_worker.WorkerSettings
else
    # Allow executing custom commands (e.g. bash, pytest)
    exec "$@"
fi