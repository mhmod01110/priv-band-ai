# 📋 Quick Reference Card

## 🚀 Starting Services

### All at Once (with tmux)
```bash
./start_all.sh
```

### Manually (4 terminals)
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Celery Worker
celery -A celery_worker worker --loglevel=info --concurrency=4

# Terminal 4: Flower Dashboard
celery -A celery_worker flower --port=5555
```

---

## 🛑 Stopping Services

```bash
./stop_all.sh
```

Or manually:
```bash
# Stop all Celery processes
pkill -f celery

# Stop FastAPI
pkill -f uvicorn

# Stop Redis (optional)
redis-cli shutdown
```

---

## 🌐 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5000 | Main UI |
| **API** | http://localhost:8000 | REST API |
| **Docs** | http://localhost:8000/docs | Swagger UI |
| **Flower** | http://localhost:5555 | Task Monitor |
| **Redis** | localhost:6379 | Database |

---

## 📡 API Endpoints

### Submit Analysis
```bash
POST /api/analyze
{
  "shop_name": "متجر الأزياء",
  "shop_specialization": "ملابس",
  "policy_type": "سياسات الاسترجاع و الاستبدال",
  "policy_text": "نص السياسة..."
}

Response:
{
  "status": "pending",
  "task_id": "abc123...",
  "idempotency_key": "..."
}
```

### Check Status
```bash
GET /api/task/{task_id}

Response:
{
  "status": "processing",
  "progress": {
    "current": 2,
    "total": 4,
    "status": "تحليل الامتثال..."
  }
}
```

### Cancel Task
```bash
DELETE /api/task/{task_id}
```

### Active Tasks
```bash
GET /api/tasks/active
```

---

## 🔧 Celery Commands

### Worker Management
```bash
# Start worker
celery -A celery_worker worker --loglevel=info

# Start with autoreload (dev)
watchmedo auto-restart --directory=./app --pattern=*.py -- \
  celery -A celery_worker worker --loglevel=info

# Start with more workers
celery -A celery_worker worker --concurrency=8

# Start with eventlet (for I/O-bound)
celery -A celery_worker worker --pool=eventlet --concurrency=100
```

### Monitoring
```bash
# List active workers
celery -A celery_worker inspect active

# Check worker status
celery -A celery_worker status

# View statistics
celery -A celery_worker inspect stats

# Ping workers
celery -A celery_worker inspect ping

# Check queue length
celery -A celery_worker inspect reserved
```

### Queue Management
```bash
# Purge all tasks (careful!)
celery -A celery_worker purge

# Revoke task
celery -A celery_worker revoke {task_id}

# Revoke and terminate
celery -A celery_worker revoke {task_id} --terminate
```

---

## 🗄️ Redis Commands

```bash
# Connect to Redis
redis-cli

# Check connection
redis-cli ping

# Monitor commands
redis-cli monitor

# View keys
redis-cli keys "*"

# Get key value
redis-cli get "key_name"

# Delete key
redis-cli del "key_name"

# Flush database (careful!)
redis-cli flushdb
```

---

## 📊 Monitoring

### Flower Dashboard
```bash
# Access: http://localhost:5555

Features:
- Real-time worker monitoring
- Task history
- Task progress
- Worker resource usage
- Retry/revoke tasks
```

### Application Logs
```bash
# Main log
tail -f logs/app.log

# Error log
tail -f logs/errors/errors_*.log

# Prompts
ls -lh logs/prompts/

# Responses
ls -lh logs/responses/
```

---

## 🐛 Troubleshooting

### Check if services are running
```bash
# Redis
redis-cli ping
# Should return: PONG

# Celery workers
celery -A celery_worker inspect active
# Should show active workers

# FastAPI
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### Common Issues

**Workers not picking tasks**
```bash
# Check broker connection
celery -A celery_worker inspect ping

# Check queue
celery -A celery_worker inspect reserved

# Restart worker
pkill -f celery
celery -A celery_worker worker --loglevel=info
```

**Tasks timing out**
```bash
# Increase limits in .env
CELERY_TASK_TIME_LIMIT=900
CELERY_TASK_SOFT_TIME_LIMIT=840

# Restart worker
```

**Memory issues**
```bash
# Restart workers after N tasks
celery -A celery_worker worker --max-tasks-per-child=100
```

---

## 🧪 Testing

### Quick Test
```bash
# Submit test task
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "shop_name": "Test Shop",
    "shop_specialization": "Clothing",
    "policy_type": "سياسات الاسترجاع و الاستبدال",
    "policy_text": "Test policy text..."
  }'

# Get task_id from response, then:
curl http://localhost:8000/api/task/{task_id}
```

### Python Test
```python
from app.celery_app.tasks import analyze_policy_task

result = analyze_policy_task.delay(
    shop_name="Test",
    shop_specialization="Clothing",
    policy_type="سياسات الاسترجاع و الاستبدال",
    policy_text="Test...",
    idempotency_key="test_123"
)

print(f"Task ID: {result.id}")
print(f"Status: {result.status}")
```

---

## 📦 Environment Variables

### Critical Settings
```bash
# AI Provider
AI_PROVIDER=openai  # or gemini

# API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## 🔐 Security

```bash
# Set Redis password
REDIS_PASSWORD=your_secure_password

# Update Celery URLs
CELERY_BROKER_URL=redis://:password@localhost:6379/1
CELERY_RESULT_BACKEND=redis://:password@localhost:6379/2
```

---

## 📈 Performance Tuning

### High Load
```bash
# More workers
celery -A celery_worker worker --concurrency=16

# Multiple worker pools
celery -A celery_worker worker --concurrency=8 &
celery -A celery_worker worker --concurrency=8 &
```

### I/O Bound Tasks
```bash
# Use eventlet
celery -A celery_worker worker --pool=eventlet --concurrency=100
```

### Memory Optimization
```bash
# Enable compression
celery -A celery_worker worker --result-compression=gzip

# Limit prefetch
celery -A celery_worker worker --prefetch-multiplier=1
```

---

## 🚢 Deployment

### Docker
```bash
docker-compose up -d
```

### Supervisor
```bash
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat
```

---

## 📞 Support

- **Logs**: `logs/app.log`
- **Flower**: http://localhost:5555
- **Docs**: `README_CELERY.md`
- **Guide**: `CELERY_SETUP_GUIDE.md`

---

## ✅ Health Check Script

Save as `check_health.sh`:

```bash
#!/bin/bash

echo "🏥 Health Check"
echo ""

echo -n "Redis: "
redis-cli ping 2>/dev/null && echo "✓" || echo "✗"

echo -n "FastAPI: "
curl -s http://localhost:8000/health > /dev/null && echo "✓" || echo "✗"

echo -n "Celery: "
celery -A celery_worker inspect ping 2>/dev/null > /dev/null && echo "✓" || echo "✗"

echo -n "Flower: "
curl -s http://localhost:5555 > /dev/null && echo "✓" || echo "✗"

echo ""
```

---

**Keep this reference handy! 📌**
