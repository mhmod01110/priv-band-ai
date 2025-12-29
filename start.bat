@echo off
echo Starting Redis...
start "Redis" redis-server

timeout /t 2

echo Starting FastAPI...
start "FastAPI" cmd /k "venv\Scripts\activate && uvicorn app.main:app --reload"

timeout /t 3

echo Starting Celery Worker...
start "Celery" cmd /k "venv\Scripts\activate && celery -A app.celery_worker worker --loglevel=info --pool=solo && celery -A app.celery_worker flower --port=5555"

echo All services started!