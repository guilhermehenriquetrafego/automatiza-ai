#!/bin/sh
# Start all processes in one container (for Render free tier)
# API (uvicorn) + Celery Worker + Celery Beat

echo "Starting AUTOMATIZA AI — API + Celery Worker + Beat"

# Start Celery Beat in background
celery -A app.tasks beat --loglevel=info --pidfile=/tmp/celerybeat.pid &
BEAT_PID=$!

# Start Celery Worker in background
celery -A app.tasks worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

# Start Uvicorn in foreground (this is the main web service process)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
