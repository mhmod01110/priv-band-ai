# 🔄 Migration Guide: Adding Celery to Existing Project

## Overview

This guide walks you through migrating your existing FastAPI project to use Celery for asynchronous task processing.

## ⏱️ Estimated Time: 30 minutes

## 📋 Checklist

- [ ] Install new dependencies
- [ ] Update configuration files
- [ ] Create Celery structure
- [ ] Update API endpoints
- [ ] Update frontend
- [ ] Test locally
- [ ] Deploy to production

---

## Step 1: Install Dependencies (5 min)

### Update requirements.txt

Add these lines to `requirements.txt`:

```txt
celery==5.3.4
flower==2.0.1
```

### Install

```bash
pip install -r requirements.txt
```

---

## Step 2: Update Configuration (5 min)

### Add to `.env`

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_SOFT_TIME_LIMIT=540
CELERY_TASK_ACKS_LATE=True
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_RESULT_EXPIRES=86400
CELERY_TASK_MAX_RETRIES=3
CELERY_TASK_DEFAULT_RETRY_DELAY=60
```

### Update `app/config.py`

Add Celery settings to Settings class:

```python
# Celery Configuration
celery_broker_url: str = "redis://localhost:6379/1"
celery_result_backend: str = "redis://localhost:6379/2"
celery_task_track_started: bool = True
celery_task_time_limit: int = 600
celery_task_soft_time_limit: int = 540
celery_task_acks_late: bool = True
celery_worker_prefetch_multiplier: int = 1
celery_result_expires: int = 86400
celery_task_max_retries: int = 3
celery_task_default_retry_delay: int = 60
```

---

## Step 3: Create Celery Structure (10 min)

### Create `app/celery_app/` directory

```bash
mkdir -p app/celery_app
touch app/celery_app/__init__.py
touch app/celery_app/celery.py
touch app/celery_app/tasks.py
```

### Create `app/celery_app/__init__.py`

```python
from .celery import celery_app

__all__ = ['celery_app']
```

### Create `app/celery_app/celery.py`

Copy from artifact: `celery_config`

### Create `app/celery_app/tasks.py`

Copy from artifact: `celery_tasks`

---

## Step 4: Create API Endpoints (5 min)

### Create `app/api/` directory

```bash
mkdir -p app/api
touch app/api/__init__.py
touch app/api/analyze.py
```

### Create `app/api/analyze.py`

Copy from artifact: `api_analyze`

---

## Step 5: Update main.py (3 min)

Replace your `app/main.py` with the updated version from artifact: `updated_main`

Key changes:
- Import new API routers
- Include analyze_router
- Update health check endpoint

---

## Step 6: Create Worker Entrypoints (2 min)

### Create `celery_worker.py` (root level)

Copy from artifact: `celery_worker_entrypoint`

### Create `celery_beat.py` (root level)

Copy from artifact: `celery_beat_entrypoint`

### Make executable

```bash
chmod +x celery_worker.py
chmod +x celery_beat.py
```

---

## Step 7: Update Frontend (5 min)

### Add `static/js/task_monitor.js`

Copy from artifact: `task_monitor_js`

### Update `static/js/app.js`

Copy from artifact: `updated_app_js`

### Update `templates/index.html`

Copy from artifact: `updated_html_template`

---

## Step 8: Create Helper Scripts (2 min)

### Create `start_all.sh`

Copy from artifact: `start_script`

```bash
chmod +x start_all.sh
```

### Create `stop_all.sh`

Copy from artifact: `stop_script`

```bash
chmod +x stop_all.sh
```

---

## Step 9: Testing (5 min)

### Start all services

```bash
./start_all.sh
```

Or manually:

**Terminal 1: Redis**
```bash
redis-server
```

**Terminal 2: FastAPI**
```bash
uvicorn app.main:app --reload
```

**Terminal 3: Celery Worker**
```bash
celery -A celery_worker worker --loglevel=info
```

**Terminal 4: Flower** (Optional)
```bash
celery -A celery_worker flower --port=5555
```

### Test the flow

1. Open http://localhost:5000
2. Fill in the form
3. Submit analysis
4. Watch progress bar update
5. View results when complete

### Check Flower

Open http://localhost:5555 to see:
- Active workers
- Task queue
- Completed tasks
- Worker statistics

---

## Step 10: Verify Everything Works

### Checklist

- [ ] FastAPI server starts without errors
- [ ] Celery worker connects to Redis
- [ ] Frontend loads correctly
- [ ] Can submit analysis task
- [ ] Progress bar updates
- [ ] Task completes successfully
- [ ] Results display correctly
- [ ] Cache works (submit same request twice)
- [ ] Flower dashboard accessible

---

## Common Issues & Solutions

### Issue: Worker can't connect to Redis

**Solution:**
```bash
# Check Redis is running
redis-cli ping

# Check Redis URL in .env
CELERY_BROKER_URL=redis://localhost:6379/1
```

### Issue: Tasks not executing

**Solution:**
```bash
# Check worker logs
celery -A celery_worker inspect active

# Restart worker
pkill -f celery
celery -A celery_worker worker --loglevel=info
```

### Issue: Frontend not updating

**Solution:**
- Clear browser cache
- Check browser console for errors
- Verify task_monitor.js is loaded
- Check network tab for API calls

### Issue: Import errors

**Solution:**
```bash
# Make sure all __init__.py files exist
touch app/celery_app/__init__.py
touch app/api/__init__.py

# Restart all services
```

---

## Rollback Plan

If something goes wrong:

1. **Keep old code**: Git branch before migration
2. **Old endpoint**: Keep `/api/analyze` with old sync code
3. **Gradual migration**: Run both sync and async versions
4. **Feature flag**: Environment variable to enable/disable Celery

Example:
```python
USE_CELERY = os.getenv('USE_CELERY', 'false').lower() == 'true'

if USE_CELERY:
    # Submit to Celery
    task = analyze_policy_task.delay(...)
else:
    # Old synchronous processing
    result = await analyze_directly(...)
```

---

## Next Steps

After successful migration:

1. ✅ **Monitor** - Watch Flower dashboard for 24 hours
2. ✅ **Optimize** - Tune worker concurrency based on load
3. ✅ **Scale** - Add more workers if needed
4. ✅ **Backup** - Setup Redis persistence
5. ✅ **Alerts** - Configure monitoring alerts
6. ✅ **Documentation** - Update team documentation

---

## Production Deployment

### Using Supervisor

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A celery_worker worker --loglevel=info
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
```

### Using Docker

See `README_CELERY.md` for docker-compose configuration.

### Using Kubernetes

Create deployment for:
- FastAPI (deployment + service)
- Celery Workers (deployment)
- Celery Beat (deployment)
- Redis (statefulset)

---

## Success Criteria

Migration is successful when:

✅ All endpoints respond correctly
✅ Tasks execute within time limits
✅ Progress tracking works smoothly
✅ Cache hits/misses work as expected
✅ No errors in logs for 24 hours
✅ Performance is better than before
✅ Team can monitor tasks easily

---

## Support

If you need help:

1. Check logs: `tail -f logs/app.log`
2. Check Flower: http://localhost:5555
3. Review this guide
4. Check Celery docs: https://docs.celeryproject.org/

---

**Good luck with your migration! 🚀**
