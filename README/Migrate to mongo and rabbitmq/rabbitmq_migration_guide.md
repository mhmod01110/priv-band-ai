# Migration Guide: Redis to RabbitMQ for Celery

This guide will help you migrate your Celery setup from Redis to RabbitMQ as the message broker, with MongoDB as the result backend.

## Why RabbitMQ?

### RabbitMQ Advantages over Redis for Celery:

✅ **Built for messaging** - RabbitMQ is designed for message queuing  
✅ **Better reliability** - Messages are persisted by default  
✅ **Advanced routing** - Complex routing patterns and exchanges  
✅ **Message acknowledgment** - Better delivery guarantees  
✅ **Monitoring tools** - Built-in management UI  
✅ **Scalability** - Better for high-volume task queues  
✅ **Priority queues** - Native support for task priorities  

### Architecture After Migration:

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   FastAPI   │────────▶│   RabbitMQ   │────────▶│   Celery    │
│   (Tasks)   │         │   (Broker)   │         │  (Workers)  │
└─────────────┘         └──────────────┘         └─────────────┘
                                                          │
                                                          ▼
                                                  ┌─────────────┐
                                                  │   MongoDB   │
                                                  │  (Results)  │
                                                  └─────────────┘
```

## Prerequisites

### 1. Install RabbitMQ

#### **Ubuntu/Debian:**
```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install curl gnupg apt-transport-https -y

# Add RabbitMQ repository
curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | sudo gpg --dearmor | sudo tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null

# Add repository
sudo tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
deb [signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb [signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
EOF

# Update and install
sudo apt-get update -y
sudo apt-get install -y erlang-base \
                        erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                        erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                        erlang-runtime-tools erlang-snmp erlang-ssl \
                        erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl

sudo apt-get install rabbitmq-server -y --fix-missing

# Start RabbitMQ
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# Enable management plugin (Web UI)
sudo rabbitmq-plugins enable rabbitmq_management
```

#### **macOS:**
```bash
# Install with Homebrew
brew install rabbitmq

# Start RabbitMQ
brew services start rabbitmq

# RabbitMQ will be available at:
# - AMQP: localhost:5672
# - Management UI: http://localhost:15672
```

#### **Windows:**
1. Download Erlang: https://www.erlang.org/downloads
2. Download RabbitMQ: https://www.rabbitmq.com/install-windows.html
3. Install both (Erlang first, then RabbitMQ)
4. RabbitMQ will start automatically as a service

#### **Docker (Development):**
```bash
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest \
  -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management
```

### 2. Verify RabbitMQ Installation

```bash
# Check if RabbitMQ is running
sudo systemctl status rabbitmq-server

# Access management UI
# Open browser: http://localhost:15672
# Default credentials: guest/guest

# Check RabbitMQ status
sudo rabbitmqctl status

# List users
sudo rabbitmqctl list_users
```

### 3. Install Python Dependencies

```bash
pip install celery[amqp,mongodb]==5.3.6
pip install kombu==5.3.5 amqp==5.2.0
```

## Migration Steps

### Step 1: Stop All Services

```bash
# Stop Celery workers
pkill -f "celery worker"

# Stop Celery beat
pkill -f "celery beat"

# Stop FastAPI
pkill -f "uvicorn"
```

### Step 2: Update Configuration Files

#### Update `.env`:
```env
# Remove old Redis settings for Celery
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Add RabbitMQ settings
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/
RABBITMQ_MANAGEMENT_PORT=15672

# Celery Broker (RabbitMQ)
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# Celery Result Backend (MongoDB)
CELERY_RESULT_BACKEND=mongodb://localhost:27017/legal_policy_analyzer
```

#### Update files:
1. ✅ `app/config.py` - Add RabbitMQ configuration
2. ✅ `app/celery_app/celery.py` - Update broker and backend URLs
3. ✅ `app/main.py` - Update health check
4. ✅ `requirements.txt` - Add RabbitMQ dependencies

### Step 3: Configure RabbitMQ User (Optional)

Create a dedicated user for production:

```bash
# Create user
sudo rabbitmqctl add_user legal_policy_user secure_password_here

# Create virtual host
sudo rabbitmqctl add_vhost legal_policy_vhost

# Set permissions
sudo rabbitmqctl set_permissions -p legal_policy_vhost legal_policy_user ".*" ".*" ".*"

# Set user as administrator (optional)
sudo rabbitmqctl set_user_tags legal_policy_user administrator

# Update .env with new credentials
RABBITMQ_USERNAME=legal_policy_user
RABBITMQ_PASSWORD=secure_password_here
RABBITMQ_VHOST=legal_policy_vhost
CELERY_BROKER_URL=amqp://legal_policy_user:secure_password_here@localhost:5672/legal_policy_vhost
```

### Step 4: Test Connection

Create a test script `test_rabbitmq.py`:

```python
import asyncio
from celery import Celery

# Test RabbitMQ connection
app = Celery(
    'test',
    broker='amqp://guest:guest@localhost:5672//',
    backend='mongodb://localhost:27017/legal_policy_analyzer'
)

@app.task
def test_task(x, y):
    return x + y

# Test
if __name__ == '__main__':
    print("Testing RabbitMQ connection...")
    try:
        # Send test task
        result = test_task.apply_async(args=[4, 4])
        print(f"Task ID: {result.id}")
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")
```

Run it:
```bash
# Start a test worker
celery -A test_rabbitmq worker --loglevel=info &

# Run test
python test_rabbitmq.py

# Kill test worker
pkill -f "celery.*test_rabbitmq"
```

### Step 5: Start Services

```bash
# 1. Start Celery Worker
celery -A app.celery_worker worker --loglevel=info --concurrency=10

# 2. Start Celery Beat (in another terminal)
celery -A app.celery_beat beat --loglevel=info

# 3. Start FastAPI (in another terminal)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 6: Verify Everything Works

```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected output should show:
# - celery: healthy
# - rabbitmq: healthy
# - mongodb: healthy
```

## Monitoring RabbitMQ

### Web Management UI

Access: **http://localhost:15672**  
Default credentials: `guest` / `guest`

Features:
- 📊 **Overview** - System health and stats
- 🔌 **Connections** - Active connections
- 📬 **Queues** - Task queues and messages
- 💱 **Exchanges** - Message routing
- 👤 **Admin** - User management

### Command Line Monitoring

```bash
# List queues
sudo rabbitmqctl list_queues name messages consumers

# List exchanges
sudo rabbitmqctl list_exchanges

# List connections
sudo rabbitmqctl list_connections

# Show queue details
sudo rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Purge a queue (clear all messages)
sudo rabbitmqctl purge_queue celery

# Delete a queue
sudo rabbitmqctl delete_queue queue_name
```

### Celery Monitoring with Flower

Install Flower (optional but recommended):

```bash
pip install flower

# Start Flower
celery -A app.celery_app.celery flower --port=5555

# Access: http://localhost:5555
```

## RabbitMQ Configuration

### Queue Settings

The default Celery queue in RabbitMQ is named `celery`. You can configure custom queues:

```python
# In celery.py
celery_app.conf.update(
    task_routes={
        'app.celery_app.tasks.analyze_policy_task': {'queue': 'analysis'},
        'app.celery_app.tasks.cleanup_old_results': {'queue': 'maintenance'},
    },
    task_default_queue='default',
)
```

### Priority Queues

Enable priority queues (0-10, higher = more priority):

```python
# In celery.py
celery_app.conf.update(
    task_queue_max_priority=10,
    task_default_priority=5,
)

# When sending task
analyze_policy_task.apply_async(args=[...], priority=9)
```

### Message TTL (Time To Live)

Set message expiration:

```python
# In celery.py
celery_app.conf.update(
    task_default_expires=3600,  # 1 hour
)
```

## Performance Tuning

### RabbitMQ Settings

Edit `/etc/rabbitmq/rabbitmq.conf`:

```conf
# Increase memory limit (default is 40% of RAM)
vm_memory_high_watermark.relative = 0.6

# Disk free space limit
disk_free_limit.absolute = 50GB

# Connection settings
heartbeat = 60
frame_max = 131072

# Enable HiPE (High Performance Erlang) - Faster but uses more memory
hipe_compile = true
```

Restart RabbitMQ after changes:
```bash
sudo systemctl restart rabbitmq-server
```

### Celery Worker Settings

Optimize worker configuration:

```bash
# Adjust concurrency based on CPU cores
celery -A app.celery_worker worker \
  --loglevel=info \
  --concurrency=10 \
  --max-tasks-per-child=1000 \
  --time-limit=600 \
  --soft-time-limit=540 \
  --pool=prefork  # or: gevent, eventlet, threads
```

### Connection Pooling

In `celery.py`:

```python
celery_app.conf.update(
    broker_pool_limit=10,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)
```

## Troubleshooting

### RabbitMQ Connection Failed

**Error:** `Connection refused to amqp://guest:**@localhost:5672//`

**Solutions:**
```bash
# 1. Check if RabbitMQ is running
sudo systemctl status rabbitmq-server

# 2. Check if port 5672 is open
sudo netstat -tulnp | grep 5672

# 3. Check firewall
sudo ufw allow 5672
sudo ufw allow 15672

# 4. Check RabbitMQ logs
sudo tail -f /var/log/rabbitmq/rabbit@*.log

# 5. Restart RabbitMQ
sudo systemctl restart rabbitmq-server
```

### MongoDB Backend Connection Failed

**Error:** `Failed to connect to MongoDB result backend`

**Solution:**
```bash
# Ensure MongoDB is running
sudo systemctl status mongod

# Check connection string format
# Correct: mongodb://localhost:27017/legal_policy_analyzer
# Incorrect: mongodb://localhost:27017 (missing database)

# Verify database exists
mongosh
> show dbs
> use legal_policy_analyzer
> db.celery_taskmeta.find()
```

### Guest User Cannot Connect Remotely

**Error:** `Access refused for user 'guest'`

**Solution:** The `guest` user can only connect from localhost. For remote connections:

```bash
# Create new user
sudo rabbitmqctl add_user myuser mypassword
sudo rabbitmqctl set_permissions -p / myuser ".*" ".*" ".*"
sudo rabbitmqctl set_user_tags myuser administrator

# Update CELERY_BROKER_URL in .env
CELERY_BROKER_URL=amqp://myuser:mypassword@localhost:5672//
```

### Tasks Stuck in Queue

**Problem:** Tasks not being processed

**Solutions:**
```bash
# 1. Check if workers are running
celery -A app.celery_app.celery inspect active

# 2. Check queue length
sudo rabbitmqctl list_queues name messages

# 3. Purge stuck messages (CAREFUL - deletes all messages!)
sudo rabbitmqctl purge_queue celery

# 4. Restart workers
pkill -f "celery worker"
celery -A app.celery_worker worker --loglevel=info
```

### Memory Issues

**Problem:** RabbitMQ using too much memory

**Solutions:**
```bash
# 1. Check memory usage
sudo rabbitmqctl status | grep memory

# 2. Set memory limit in /etc/rabbitmq/rabbitmq.conf
vm_memory_high_watermark.relative = 0.4

# 3. Enable memory alarms
sudo rabbitmqctl set_vm_memory_high_watermark 0.4

# 4. Restart RabbitMQ
sudo systemctl restart rabbitmq-server
```

## Data Persistence

### RabbitMQ Durability

Messages are persisted by default, but ensure:

```python
# In celery.py
celery_app.conf.update(
    task_publish_retry=True,
    task_publish_retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    },
)
```

### MongoDB Result Storage

Results are stored in MongoDB collections:
- `celery_taskmeta` - Task results
- `celery_groupmeta` - Group results

View results:
```javascript
// In mongosh
use legal_policy_analyzer

// Find recent tasks
db.celery_taskmeta.find().sort({_id: -1}).limit(5)

// Count total tasks
db.celery_taskmeta.countDocuments()

// Find failed tasks
db.celery_taskmeta.find({status: "FAILURE"})
```

## Production Deployment

### RabbitMQ Cluster (High Availability)

For production, set up a RabbitMQ cluster:

```bash
# On node1
sudo rabbitmqctl stop_app
sudo rabbitmqctl reset
sudo rabbitmqctl start_app

# On node2 and node3
sudo rabbitmqctl stop_app
sudo rabbitmqctl join_cluster rabbit@node1
sudo rabbitmqctl start_app

# Enable HA policy
sudo rabbitmqctl set_policy ha-all ".*" '{"ha-mode":"all"}'
```

### Systemd Services

Create systemd services for automatic startup:

**`/etc/systemd/system/celery-worker.service`:**
```ini
[Unit]
Description=Celery Worker
After=network.target rabbitmq-server.service mongod.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/legal_policy_analyzer
ExecStart=/path/to/venv/bin/celery -A app.celery_worker worker \
  --loglevel=info \
  --concurrency=10 \
  --logfile=/var/log/celery/worker.log \
  --pidfile=/var/run/celery/worker.pid

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/celery-beat.service`:**
```ini
[Unit]
Description=Celery Beat
After=network.target rabbitmq-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/legal_policy_analyzer
ExecStart=/path/to/venv/bin/celery -A app.celery_beat beat \
  --loglevel=info \
  --logfile=/var/log/celery/beat.log \
  --pidfile=/var/run/celery/beat.pid

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
```

## Performance Comparison

| Metric | Redis | RabbitMQ |
|--------|-------|----------|
| **Message Delivery** | Fire-and-forget | Acknowledged |
| **Persistence** | Optional | Default |
| **Message Routing** | Basic | Advanced (exchanges) |
| **Priority Queues** | Limited | Native support |
| **Monitoring** | CLI only | Web UI + CLI |
| **Message Size** | ~512MB | ~2GB |
| **Throughput** | Higher | High |
| **Reliability** | Good | Excellent |
| **Best For** | Simple queues | Complex workflows |

## Verification Checklist

- [ ] RabbitMQ is installed and running
- [ ] Management UI is accessible (http://localhost:15672)
- [ ] MongoDB is running (for result backend)
- [ ] Updated configuration files
- [ ] Installed new dependencies
- [ ] Celery workers start without errors
- [ ] Tasks can be submitted successfully
- [ ] Tasks are processed and results stored
- [ ] Health check shows all components healthy
- [ ] RabbitMQ queues visible in management UI
- [ ] No error logs in RabbitMQ or Celery

## Next Steps

1. ✅ Monitor RabbitMQ performance
2. ✅ Set up alerts for queue length
3. ✅ Configure log rotation
4. ✅ Set up backups (MongoDB + RabbitMQ definitions)
5. ✅ Implement monitoring (Flower, Prometheus, etc.)
6. ✅ Consider clustering for high availability

## Support Resources

- **RabbitMQ Docs**: https://www.rabbitmq.com/documentation.html
- **Celery with RabbitMQ**: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html
- **Management Plugin**: https://www.rabbitmq.com/management.html
- **Monitoring**: https://www.rabbitmq.com/monitoring.html

---

**Summary**: You've successfully migrated from Redis to RabbitMQ for Celery message brokering, with MongoDB handling result storage. RabbitMQ provides better reliability, monitoring, and advanced features for your production workload.
