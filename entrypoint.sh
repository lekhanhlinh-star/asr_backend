#!/usr/bin/env sh

set -e

echo "🟢 Starting Celery worker..."
celery -A app.celery_app.celery worker --loglevel=info --concurrency=1  --pool=solo &

sleep 5

echo "🟢 Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port=8001
