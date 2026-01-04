# Migration Guide: Redis to MongoDB

This guide will help you migrate your Legal Policy Analyzer from Redis to MongoDB for caching.

## Prerequisites

### 1. Install MongoDB

**Ubuntu/Debian:**
```bash
# Import MongoDB public GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0
```

**Windows:**
Download and install from: https://www.mongodb.com/try/download/community

### 2. Install Python Dependencies

```bash
pip install motor==3.3.2 pymongo==4.6.1
```

## Migration Steps

### Step 1: Update Configuration

1. **Update `.env` file:**
```env
# Remove old Redis settings (keep only for Celery)
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_DB=0
# etc.

# Add MongoDB settings
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=legal_policy_analyzer
MONGODB_USERNAME=
MONGODB_PASSWORD=
MONGODB_AUTH_SOURCE=admin
MONGODB_MIN_POOL_SIZE=10
MONGODB_MAX_POOL_SIZE=100
MONGODB_TIMEOUT=5000
```

### Step 2: Replace Files

Replace the following files with the MongoDB versions:

1. `app/config.py` - Updated configuration
2. `app/services/mongodb_client.py` - **NEW FILE**
3. `app/services/idempotency_service.py` - MongoDB version
4. `app/services/graceful_degradation.py` - MongoDB version
5. `app/services/quota_tracker.py` - MongoDB version
6. Update health check in `app/main.py`

### Step 3: Verify MongoDB Connection

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Connect to MongoDB shell
mongosh

# In MongoDB shell:
> use legal_policy_analyzer
> db.stats()
```

### Step 4: Create MongoDB Indexes (Automatic)

The indexes will be created automatically on first connection. Verify:

```javascript
// In MongoDB shell
use legal_policy_analyzer

// Check indexes
db.idempotency.getIndexes()
db.graceful_fallback.getIndexes()
db.quota.getIndexes()
```

Expected indexes:
- **idempotency**: `key` (unique), `expires_at` (TTL)
- **graceful_fallback**: `policy_type + content_hash` (unique), `expires_at` (TTL)
- **quota**: `provider + period_type + period_key` (unique), `expires_at` (TTL)

### Step 5: Test the Application

```bash
# Start the application
python -m app.main

# Or with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check the health endpoint:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Legal Policy Analyzer",
  "celery": {
    "status": "healthy",
    "workers": 1
  },
  "mongodb": {
    "status": "healthy",
    "stats": {
      "connected": true,
      "database": "legal_policy_analyzer",
      "collections": {
        "idempotency": 0,
        "graceful_fallback": 0,
        "quota": 0
      }
    }
  }
}
```

### Step 6: Start Celery Workers

Celery still uses Redis for broker/backend (this is recommended):

```bash
# Start Celery worker
celery -A app.celery_worker worker --loglevel=info

# Start Celery Beat (in another terminal)
celery -A app.celery_beat beat --loglevel=info
```

## Data Migration (Optional)

If you have existing data in Redis that you want to migrate to MongoDB:

### Export from Redis

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Get all idempotency keys
keys = r.keys('idempotency:*')

data_to_migrate = []
for key in keys:
    value = r.get(key)
    if value:
        try:
            data_to_migrate.append({
                'key': key,
                'value': json.loads(value)
            })
        except:
            pass

print(f"Found {len(data_to_migrate)} records to migrate")
```

### Import to MongoDB

```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta

async def migrate_data(data_to_migrate):
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['legal_policy_analyzer']
    collection = db['idempotency']
    
    for item in data_to_migrate:
        document = {
            'key': item['key'],
            'value': item['value'],
            'expires_at': datetime.utcnow() + timedelta(days=1),
            'created_at': datetime.utcnow(),
            'ttl': 86400
        }
        
        await collection.update_one(
            {'key': item['key']},
            {'$set': document},
            upsert=True
        )
    
    print(f"Migrated {len(data_to_migrate)} records")

# Run migration
asyncio.run(migrate_data(data_to_migrate))
```

## Verification Checklist

- [ ] MongoDB is running and accessible
- [ ] Application starts without errors
- [ ] Health check shows MongoDB as healthy
- [ ] Can submit analysis requests
- [ ] Results are cached in MongoDB (check with `db.idempotency.find()`)
- [ ] Graceful degradation works (check `db.graceful_fallback.find()`)
- [ ] Quota tracking works (check `db.quota.find()`)
- [ ] Celery workers are running
- [ ] Celery tasks complete successfully

## Monitoring MongoDB

### View Collections

```javascript
// In MongoDB shell
use legal_policy_analyzer

// View all collections
show collections

// Count documents
db.idempotency.countDocuments()
db.graceful_fallback.countDocuments()
db.quota.countDocuments()

// View recent documents
db.idempotency.find().sort({created_at: -1}).limit(5)
```

### Monitor Performance

```javascript
// Database stats
db.stats()

// Collection stats
db.idempotency.stats()

// Current operations
db.currentOp()
```

## Troubleshooting

### MongoDB Connection Failed

**Error:** `Failed to connect to MongoDB`

**Solution:**
1. Check if MongoDB is running: `sudo systemctl status mongod`
2. Check connection string in `.env`
3. Verify firewall rules: `sudo ufw allow 27017`

### Index Creation Failed

**Error:** `Failed to create indexes`

**Solution:**
```javascript
// Manually create indexes in MongoDB shell
use legal_policy_analyzer

db.idempotency.createIndex({key: 1}, {unique: true})
db.idempotency.createIndex({expires_at: 1}, {expireAfterSeconds: 0})

db.graceful_fallback.createIndex({policy_type: 1, content_hash: 1}, {unique: true})
db.graceful_fallback.createIndex({expires_at: 1}, {expireAfterSeconds: 0})

db.quota.createIndex({provider: 1, period_type: 1, period_key: 1}, {unique: true})
db.quota.createIndex({expires_at: 1}, {expireAfterSeconds: 0})
```

### TTL Index Not Working

**Problem:** Old documents not being deleted automatically

**Solution:**
```javascript
// Check TTL monitor
db.serverStatus().metrics.ttl

// Verify index has expireAfterSeconds
db.idempotency.getIndexes()

// TTL monitor runs every 60 seconds by default
```

## Performance Comparison

| Metric | Redis | MongoDB |
|--------|-------|---------|
| Write Speed | ~50,000 ops/sec | ~10,000 ops/sec |
| Read Speed | ~100,000 ops/sec | ~50,000 ops/sec |
| Data Persistence | Optional | Always |
| Querying | Limited | Rich queries |
| Scalability | Clustering | Replica Sets + Sharding |
| Memory Usage | All in RAM | Configurable |

## Advantages of MongoDB Over Redis

✅ **Persistent by default** - No data loss on restart  
✅ **Rich queries** - Complex filtering and aggregation  
✅ **Better for large datasets** - Not limited by RAM  
✅ **Built-in TTL** - Automatic document expiration  
✅ **Easier to inspect** - Human-readable documents  
✅ **Better for analytics** - Complex aggregation pipeline  

## Notes

- **Redis is still used for Celery** - This is recommended and won't change
- **MongoDB TTL indices** - Documents expire automatically after `expires_at`
- **Connection pooling** - MongoDB uses connection pooling by default
- **Async operations** - All MongoDB operations are async using Motor

## Support

If you encounter issues during migration:

1. Check logs: `tail -f logs/app.log`
2. Check MongoDB logs: `sudo tail -f /var/log/mongodb/mongod.log`
3. Verify indexes: Run the index verification commands above
4. Test connection: Use the health check endpoint

## Rollback (If Needed)

If you need to rollback to Redis:

1. Stop the application
2. Restore old Redis-based files
3. Update `.env` to use Redis configuration
4. Restart the application

The data in MongoDB will remain and can be migrated again later.
