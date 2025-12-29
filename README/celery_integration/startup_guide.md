# 🚀 Celery Integration Setup Guide

## Prerequisites

```bash
# 1. Install Redis (if not already installed)
# macOS
brew install redis

# Ubuntu/Debian
sudo apt-get install redis-server

# Windows
# Download from: https://github.com/microsoftarchive/redis/releases
```

## Installation Steps

### 1. Update Dependencies

```bash
pip install -r requirements.txt
```

### 2. Update Environment Variables

Copy the new `.env.example` and configure:

```bash
cp .env.example .env
nano .env
```

Make sure these Celery variables are set:

```bash
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 3. Start Redis

```bash
# Start Redis server
redis-server

# Test Redis connection
redis-cli ping
# Should return: PONG
```

## Running the Application

You need **4 terminal windows**:

### Terminal 1: Redis Server

```bash
redis-server
```

### Terminal 2: FastAPI Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Terminal 3: Celery Worker

```bash
# Development
celery -A celery_worker worker --loglevel=info --concurrency=4

# With autoreload (development)
watchmedo auto-restart --directory=./app --pattern=*.py --recursive -- celery -A celery_worker worker --loglevel=info
```

### Terminal 4: Celery Beat (Optional - for scheduled tasks)

```bash
celery -A celery_beat beat --loglevel=info
```

### Terminal 5: Flower (Optional - monitoring dashboard)

```bash
celery -A celery_worker flower --port=5555
```

Access Flower at: http://localhost:5555

## Quick Test

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Submit analysis task
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "shop_name": "متجر الاختبار",
    "shop_specialization": "ملابس",
    "policy_type": "سياسات الاسترجاع و الاستبدال",
    "policy_text": "يحق للعميل إرجاع المنتج خلال 7 أيام..."
  }'

# Check task status (use task_id from above)
curl http://localhost:8000/api/task/{task_id}
```

## Architecture Flow

```
1. User submits form → FastAPI receives request
2. FastAPI submits task to Celery → Returns task_id immediately
3. Celery worker picks up task → Starts analysis
4. Frontend polls task status every 2 seconds
5. Worker updates task progress → Frontend shows progress bar
6. Task completes → Frontend displays results
```

## Monitoring

### Check Active Workers

```bash
celery -A celery_worker inspect active
```

### Check Task Queue

```bash
celery -A celery_worker inspect reserved
```

### View Statistics

```bash
celery -A celery_worker inspect stats
```

### Purge All Tasks (careful!)

```bash
celery -A celery_worker purge
```

## Production Deployment

### Using Supervisor

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A celery_worker worker --loglevel=info --concurrency=8
directory=/path/to/project
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_err.log
autostart=true
autorestart=true
startsecs=10

[program:celery_beat]
command=/path/to/venv/bin/celery -A celery_beat beat --loglevel=info
directory=/path/to/project
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat_err.log
autostart=true
autorestart=true
startsecs=10
```

Then:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat
```

### Using Docker

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis

  celery_worker:
    build: .
    command: celery -A celery_worker worker --loglevel=info --concurrency=4
    environment:
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis

  celery_beat:
    build: .
    command: celery -A celery_beat beat --loglevel=info
    environment:
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis

  flower:
    build: .
    command: celery -A celery_worker flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis

volumes:
  redis_data:
```

## Troubleshooting

### Issue: Tasks not executing

**Check:**
1. Redis is running: `redis-cli ping`
2. Worker is running: `celery -A celery_worker inspect active`
3. Task is submitted: Check Flower dashboard

### Issue: Tasks timing out

**Solution:**
Increase time limits in `.env`:

```bash
CELERY_TASK_TIME_LIMIT=900  # 15 minutes
CELERY_TASK_SOFT_TIME_LIMIT=840  # 14 minutes
```

### Issue: Memory leaks

**Solution:**
Restart workers after N tasks:

```bash
celery -A celery_worker worker --max-tasks-per-child=100
```

### Issue: Task not found

**Solution:**
Make sure task imports are correct in `celery.py`:

```python
include=['app.celery_app.tasks']
```

## Performance Tuning

### For Heavy Load

```bash
# Increase workers
celery -A celery_worker worker --concurrency=16

# Use eventlet/gevent for I/O bound tasks
celery -A celery_worker worker --pool=eventlet --concurrency=100
```

### For Memory Optimization

```bash
# Enable result compression
celery -A celery_worker worker --result-compression=gzip

# Limit prefetch
celery -A celery_worker worker --prefetch-multiplier=1
```

## Next Steps

1. ✅ Test locally with all 4 terminals running
2. ✅ Submit a test analysis via UI
3. ✅ Monitor progress in Flower dashboard
4. ✅ Check logs for any errors
5. ✅ Test cache behavior (submit same request twice)
6. ✅ Test force refresh feature
7. ✅ Deploy to production with Supervisor/Docker

## Support

If you encounter issues:

1. Check Redis: `redis-cli ping`
2. Check worker logs
3. Check Flower dashboard: http://localhost:5555
4. Review `logs/` directory
5. Test with `celery -A celery_worker inspect ping`

---

**Happy Analyzing! 🎉**
