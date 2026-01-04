# Quick Reference: Redis to MongoDB Migration

## Files Changed

### New Files
- ✨ `app/services/mongodb_client.py` - MongoDB client and helper methods

### Modified Files
1. 📝 `.env.example` - Added MongoDB configuration
2. 📝 `app/config.py` - Added MongoDB settings
3. 🔄 `app/services/idempotency_service.py` - Using MongoDB instead of Redis
4. 🔄 `app/services/graceful_degradation.py` - Using MongoDB instead of Redis
5. 🔄 `app/services/quota_tracker.py` - Using MongoDB instead of Redis
6. 🔄 `app/main.py` - Updated health check to show MongoDB stats

### Dependencies
```bash
# New
motor==3.3.2  # Async MongoDB driver
pymongo==4.6.1

# Redis still needed for Celery only
redis==5.0.1
```

## Configuration Changes

### Before (Redis)
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_SSL=False
REDIS_DECODE_RESPONSES=True
```

### After (MongoDB)
```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=legal_policy_analyzer
MONGODB_USERNAME=
MONGODB_PASSWORD=
MONGODB_AUTH_SOURCE=admin
MONGODB_MIN_POOL_SIZE=10
MONGODB_MAX_POOL_SIZE=100
MONGODB_TIMEOUT=5000
```

## Code Changes

### Idempotency Service

**Before (Redis):**
```python
import redis.asyncio as redis

self.redis_client = redis.Redis(
    host=self.settings.redis_host,
    port=self.settings.redis_port,
    # ...
)

await self.redis_client.setex(key, ttl, json.dumps(result))
cached_data = await self.redis_client.get(key)
```

**After (MongoDB):**
```python
from app.services.mongodb_client import mongodb_client

self.mongodb = mongodb_client

await collection.update_one(
    {"key": key},
    {"$set": document},
    upsert=True
)

document = await collection.find_one({
    "key": key,
    "expires_at": {"$gt": datetime.utcnow()}
})
```

### Key Differences

| Feature | Redis | MongoDB |
|---------|-------|---------|
| **Data Structure** | Key-Value | Document-based |
| **TTL** | `SETEX` command | `expires_at` field + TTL index |
| **Queries** | Simple key lookups | Rich filtering |
| **Atomic Ops** | `INCR`, `INCRBY` | `$inc` operator |
| **Expiration** | Built-in TTL | TTL index (runs every 60s) |
| **Storage** | In-memory | Disk + memory cache |

## MongoDB Collections Structure

### `idempotency` Collection
```javascript
{
  _id: ObjectId("..."),
  key: "idempotency:abc123...",
  value: {
    success: true,
    result: { /* analysis result */ }
  },
  expires_at: ISODate("2024-01-05T10:00:00Z"),
  created_at: ISODate("2024-01-04T10:00:00Z"),
  ttl: 86400
}
```

### `graceful_fallback` Collection
```javascript
{
  _id: ObjectId("..."),
  policy_type: "سياسات الاسترجاع و الاستبدال",
  content_hash: "a3f5c9e...",
  result: { /* cached analysis */ },
  expires_at: ISODate("2024-01-11T10:00:00Z"),
  cached_at: ISODate("2024-01-04T10:00:00Z"),
  ttl: 604800
}
```

### `quota` Collection
```javascript
{
  _id: ObjectId("..."),
  provider: "openai",
  period_type: "daily",
  period_key: "2024-01-04",
  tokens: 15000,
  requests: 50,
  expires_at: ISODate("2024-01-06T00:00:00Z"),
  created_at: ISODate("2024-01-04T10:00:00Z"),
  last_updated: ISODate("2024-01-04T15:30:00Z")
}
```

## Common MongoDB Operations

### View Data
```javascript
// In mongosh
use legal_policy_analyzer

// Count documents
db.idempotency.countDocuments()

// Find recent
db.idempotency.find().sort({created_at: -1}).limit(5).pretty()

// Find by key
db.idempotency.findOne({key: "idempotency:abc123..."})

// Find active (not expired)
db.idempotency.find({expires_at: {$gt: new Date()}}).count()
```

### Clear Cache
```javascript
// Clear all idempotency cache
db.idempotency.deleteMany({})

// Clear specific provider quota
db.quota.deleteMany({provider: "openai"})

// Clear expired documents (usually automatic)
db.idempotency.deleteMany({expires_at: {$lt: new Date()}})
```

### Check Indexes
```javascript
// View indexes
db.idempotency.getIndexes()

// Example output:
[
  { key: { _id: 1 }, name: "_id_" },
  { key: { key: 1 }, name: "key_1", unique: true },
  { key: { expires_at: 1 }, name: "expires_at_1", expireAfterSeconds: 0 }
]
```

## API Compatibility

The external API remains **100% compatible**. No changes needed in:
- Frontend code
- API clients
- Request/response formats
- Endpoints

Only internal storage mechanism changed from Redis to MongoDB.

## Performance Notes

### Redis vs MongoDB for This Use Case

**When Redis is Better:**
- Pure caching with simple key-value
- Very high-speed read/write (100k+ ops/sec)
- Temporary data only

**When MongoDB is Better:**
- Need data persistence
- Complex queries on cached data
- Large datasets (not limited by RAM)
- Analytics and reporting
- Our use case ✅

### Optimization Tips

1. **Indexes are critical** - Ensure all indexes are created
2. **Use projections** - Only fetch needed fields
3. **Connection pooling** - Already configured (10-100 connections)
4. **TTL monitoring** - MongoDB runs TTL cleanup every 60 seconds
5. **Avoid large documents** - Keep analysis results reasonable (<1MB)

## Testing Checklist

- [ ] MongoDB is running
- [ ] All indexes created successfully
- [ ] Application connects to MongoDB
- [ ] Can store and retrieve idempotency keys
- [ ] TTL expiration works (wait 60+ seconds)
- [ ] Graceful degradation caching works
- [ ] Quota tracking increments correctly
- [ ] Health check shows MongoDB status
- [ ] Celery tasks complete successfully
- [ ] No Redis connection errors (except Celery broker)

## Quick Commands Reference

```bash
# Install dependencies
pip install motor==3.3.2 pymongo==4.6.1

# Start MongoDB
sudo systemctl start mongod

# Check MongoDB status
sudo systemctl status mongod

# Connect to MongoDB shell
mongosh

# View logs
tail -f /var/log/mongodb/mongod.log

# Backup database
mongodump --db legal_policy_analyzer --out /backup/

# Restore database
mongorestore --db legal_policy_analyzer /backup/legal_policy_analyzer/
```

## Next Steps

1. ✅ Install MongoDB
2. ✅ Update configuration files
3. ✅ Install Python dependencies
4. ✅ Replace service files
5. ✅ Test application
6. ✅ Monitor performance
7. ✅ Set up backups (optional)

## Support Resources

- **MongoDB Docs**: https://docs.mongodb.com/
- **Motor Docs**: https://motor.readthedocs.io/
- **MongoDB Atlas** (Cloud): https://www.mongodb.com/atlas
- **Monitoring**: MongoDB Compass (GUI tool)

---

**Summary**: Redis → MongoDB migration is complete. All caching functionality preserved with added benefits of persistence, rich queries, and better scalability. Celery still uses Redis (recommended).
