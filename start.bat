@echo off

timeout /t 2

echo Starting FastAPI...
start "FastAPI" cmd /k "venv\Scripts\activate && uvicorn app.main:app --reload"

timeout /t 3

echo Starting Celery Worker...
start "Celery" cmd /k "venv\Scripts\activate && celery -A app.celery_worker:celery_app worker -l info -P gevent -c 10 -E && celery -A app.celery_worker flower --port=5555"


timeout /t 3

echo Starting Celery Flower...
start "Celery Flower" cmd /k "venv\Scripts\activate && celery -A app.celery_worker flower --port=5555"


echo All services started!

@REM # Terminal 1
@REM celery -A your_project worker -n worker1@%h --concurrency=5

@REM # Terminal 2
@REM celery -A your_project worker -n worker2@%h --concurrency=5

@REM # Terminal 3
@REM celery -A your_project worker -n worker3@%h --concurrency=5