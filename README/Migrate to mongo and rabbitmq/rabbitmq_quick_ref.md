# Quick Reference: Redis to RabbitMQ Migration

## Architecture Overview

### Before (Redis)
```
FastAPI → Redis (Broker) → Celery Workers → Redis (Results)
```

### After (RabbitMQ + MongoDB)
```
FastAPI → RabbitMQ (Broker) → Celery Workers → MongoDB (Results)
```

## Quick Installation

### Ubuntu/Debian
```bash
# Install RabbitMQ
sudo apt-get install rabbitmq-server -y
sudo systemctl start rabbitmq-server
sudo rabbitmq-plugins enable rabbitmq_management

# Install Python dependencies
pip install celery[amqp,mongodb]==5.3.6 kombu==5.3.5 amqp==5.2.0
```

### macOS
```bash
brew install rabbitmq
brew services start rabbitmq
pip install celery[amqp,mongodb]==5.3.6
```

### Docker
```bash
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3-management
```

## Configuration Changes

### .env File
```env
# OLD (Redis)
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/2

# NEW (RabbitMQ + MongoDB)
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=mongodb://localhost:27017/legal_policy_analyzer
```

## Key URLs and Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| RabbitMQ AMQP | 5672 | `amqp://localhost:5672` | Celery broker |
| RabbitMQ Management | 15672 | `http://localhost:15672` | Web UI |
| MongoDB | 27017 | `mongodb://localhost:27017` | Result backend |

## Common Commands

### RabbitMQ Management
```bash
# Check status
sudo systemctl status rabbitmq-server

# Start/Stop/Restart
sudo systemctl start rabbitmq-server
sudo systemctl stop rabbitmq-server
sudo systemctl restart rabbitmq-server

# Enable management UI
sudo rabbitmq-plugins enable rabbitmq_management

# List queues
sudo rabbitmqctl list_queues

# Purge queue
sudo rabbitmqctl purge_queue celery

# Check connections
sudo rabbitmqctl list_connections
```

### Celery Commands
```bash
# Start worker
celery -A app.celery_worker worker --loglevel=info

# Start beat scheduler
celery -A app.celery_beat beat --loglevel=info

# Inspect active tasks
celery -A app.celery_app.celery inspect active

# Inspect registered tasks
celery -A app.celery_app.celery inspect registered

# Purge all tasks
celery -A app.celery_app.celery purge

# Start Flower monitoring
celery -A app.celery_app.celery flower
```

### MongoDB Commands
```javascript
// In mongosh
use legal_policy_analyzer

// View task results
db.celery_taskmeta.find().sort({_id: -1}).limit(5)

// Count tasks
db.celery_taskmeta.countDocuments()

// Find failed tasks
db.celery_taskmeta.find({status: "FAILURE"})

// Clear old results
db.celery_taskmeta.deleteMany({})
```

## Monitoring URLs

| Tool | URL | Credentials |
|------|-----|-------------|
| RabbitMQ Management | http://localhost:15672 | guest / guest |
| Flower (optional) | http://localhost:5555 | - |
| Health Check | http://localhost:8000/health | - |

## File Changes Summary

### Modified Files
- ✅ `.env` - RabbitMQ configuration
- ✅ `app/config.py` - RabbitMQ settings
- ✅ `app/celery_app/celery.py` - Broker and backend URLs
- ✅ `app/main.py` - Health check with RabbitMQ
- ✅ `requirements.txt` - RabbitMQ dependencies

### No Changes Needed
- ✅ `app/celery_app/tasks.py` - Works as-is
- ✅ `app/api/analyze.py` - No changes
- ✅ All other application code

## Troubleshooting Quick Fixes

### Connection Refused
```bash
# Check if RabbitMQ is running
sudo systemctl status rabbitmq-server

# Restart RabbitMQ
sudo systemctl restart rabbitmq-server
```

### Guest User Cannot Connect
```bash
# Create new user
sudo rabbitmqctl add_user myuser mypass
sudo rabbitmqctl set_permissions -p / myuser ".*" ".*" ".*"

# Update .env
CELERY_BROKER_URL=amqp://myuser:mypass@localhost:5672//
```

### Tasks Not Processing
```bash
# Check workers
celery -A app.celery_app.celery inspect active

# Check queues
sudo rabbitmqctl list_queues name messages

# Restart workers
pkill -f "celery worker"
celery -A app.celery_worker worker --loglevel=info
```

### Port Already in Use
```bash
# Check what's using port 5672
sudo lsof -i :5672

# Kill process if needed
sudo kill -9 <PID>
```

## Testing

### Test RabbitMQ Connection
```python
# test_rabbitmq.py
from celery import Celery

app = Celery(broker='amqp://guest:guest@localhost:5672//')

@app.task
def add(x, y):
    return x + y

if __name__ == '__main__':
    result = add.apply_async((4, 4))
    print(f"Task sent: {result.id}")
```

```bash
# Run worker
celery -A test_rabbitmq worker &

# Test
python test_rabbitmq.py
```

### Test Health Check
```bash
curl http://localhost:8000/health | jq
```

Expected output:
```json
{
  "status": "healthy",
  "components": {
    "celery": {"status": "healthy"},
    "rabbitmq": {"status": "healthy"},
    "mongodb": {"status": "healthy"}
  }
}
```

## Performance Tips

### RabbitMQ Settings
```conf
# /etc/rabbitmq/rabbitmq.conf
vm_memory_high_watermark.relative = 0.6
disk_free_limit.absolute = 50GB
heartbeat = 60
```

### Celery Worker Optimization
```bash
celery -A app.celery_worker worker \
  --concurrency=10 \
  --max-tasks-per-child=1000 \
  --pool=prefork
```

### Priority Queues
```python
# In celery.py
celery_app.conf.task_queue_max_priority = 10

# When sending task
task.apply_async(priority=9)
```

## Default Credentials

| Service | Username | Password | Access |
|---------|----------|----------|--------|
| RabbitMQ | guest | guest | localhost only |
| MongoDB | - | - | no auth by default |

**⚠️ Production:** Change default credentials!

## Useful Monitoring Queries

### RabbitMQ Stats
```bash
# Queue stats
sudo rabbitmqctl list_queues name messages consumers memory

# Connection stats
sudo rabbitmqctl list_connections name peer_host peer_port state

# Channel stats
sudo rabbitmqctl list_channels connection name number
```

### MongoDB Result Stats
```javascript
// Average task duration
db.celery_taskmeta.aggregate([
  {$match: {status: "SUCCESS"}},
  {$group: {_id: null, avg: {$avg: "$result.duration"}}}
])

// Tasks by status
db.celery_taskmeta.aggregate([
  {$group: {_id: "$status", count: {$sum: 1}}}
])
```

## Migration Checklist

- [ ] Install RabbitMQ
- [ ] Enable management plugin
- [ ] Verify RabbitMQ is running
- [ ] Install Python dependencies
- [ ] Update .env configuration
- [ ] Update config.py
- [ ] Update celery.py
- [ ] Update main.py health check
- [ ] Test RabbitMQ connection
- [ ] Start Celery workers
- [ ] Submit test task
- [ ] Verify task completion
- [ ] Check RabbitMQ management UI
- [ ] Check MongoDB results
- [ ] Verify health check endpoint

## Quick Links

- 📚 RabbitMQ Docs: https://www.rabbitmq.com/documentation.html
- 📊 Management Plugin: https://www.rabbitmq.com/management.html
- 🐍 Celery Docs: https://docs.celeryq.dev/
- 🌸 Flower: https://flower.readthedocs.io/

## Support

If issues occur:
1. Check logs: `sudo tail -f /var/log/rabbitmq/rabbit@*.log`
2. Check Celery logs: `tail -f logs/app.log`
3. Verify all services are running
4. Test connections individually

---

**Pro Tip:** Access RabbitMQ Management UI at http://localhost:15672 for real-time monitoring and debugging. It's much more powerful than Redis CLI!
