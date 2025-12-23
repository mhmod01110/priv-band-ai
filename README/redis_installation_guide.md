# دليل تثبيت وإعداد نظام Idempotency

## 📋 المتطلبات الأساسية

### 1. تثبيت Redis

#### على Windows:
```bash
# استخدم Windows Subsystem for Linux (WSL) أو قم بتنزيل Redis من:
# https://github.com/microsoftarchive/redis/releases

# أو استخدم Docker:
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

#### على macOS:
```bash
brew install redis
brew services start redis
```

#### على Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

### 2. التحقق من تشغيل Redis
```bash
redis-cli ping
# يجب أن ترى: PONG
```

---

## 🚀 خطوات التثبيت

### الخطوة 1: تحديث المكتبات
```bash
pip install -r requirements.txt
```

### الخطوة 2: إعداد ملف .env
```bash
cp .env.example .env
```

قم بتحرير `.env` وإضافة إعدادات Redis:
```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_SSL=false

# Idempotency Settings
IDEMPOTENCY_TTL=86400        # 24 hours
IDEMPOTENCY_ENABLE=true      # تفعيل/تعطيل النظام
```

### الخطوة 3: اختبار الاتصال
```python
# test_redis_connection.py
import asyncio
from app.services.idempotency_service import idempotency_service

async def test():
    await idempotency_service.connect()
    stats = await idempotency_service.get_stats()
    print("Stats:", stats)
    await idempotency_service.disconnect()

asyncio.run(test())
```

---

## 🔧 خيارات الإعداد

### 1. إعداد بسيط (Development)
```bash
# Redis محلي بدون password
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
IDEMPOTENCY_ENABLE=true
```

### 2. إعداد للإنتاج (Production)
```bash
# Redis مُأمّن مع SSL
REDIS_HOST=your-redis-server.com
REDIS_PORT=6380
REDIS_PASSWORD=your-secure-password-here
REDIS_SSL=true
IDEMPOTENCY_ENABLE=true
IDEMPOTENCY_TTL=43200  # 12 hours
```

### 3. إعداد Redis Cloud (مثل Upstash)
```bash
REDIS_HOST=your-region.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=your-upstash-password
REDIS_SSL=true
```

### 4. تعطيل Idempotency (للتطوير فقط)
```bash
IDEMPOTENCY_ENABLE=false
```

---

## 📊 التحقق من عمل النظام

### 1. فحص الـ Health Check
```bash
curl http://localhost:8000/health
```

يجب أن ترى:
```json
{
  "status": "healthy",
  "service": "Legal Policy Analyzer",
  "idempotency": {
    "enabled": true,
    "connected": true,
    "total_keys": 5
  }
}
```

### 2. اختبار Idempotency
قم بإرسال نفس الطلب مرتين:
```bash
# الطلب الأول
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test-123" \
  -d '{...}'

# الطلب الثاني (نفس المفتاح)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test-123" \
  -d '{...}'
```

يجب أن يحتوي الرد الثاني على:
- Header: `X-Cache-Status: HIT`
- الاستجابة فورية (من الـ cache)

### 3. مراقبة Logs
```bash
tail -f logs/app.log | grep "idempotency\|cache"
```

يجب أن ترى:
```
✅ Redis connected successfully for idempotency
✅ Cache HIT for key: idempotency:abc123...
```

---

## 🔍 استكشاف الأخطاء

### مشكلة: Redis connection failed

**الحل:**
```bash
# تحقق من تشغيل Redis
redis-cli ping

# تحقق من المنفذ
netstat -an | grep 6379

# إعادة تشغيل Redis
# Linux/Mac:
sudo systemctl restart redis

# Docker:
docker restart redis
```

### مشكلة: Permission denied

**الحل:**
```bash
# تحقق من صلاحيات Redis
sudo chown redis:redis /var/lib/redis
sudo chmod 755 /var/lib/redis
```

### مشكلة: Authentication failed

**الحل:**
```bash
# تحقق من كلمة المرور في Redis config
redis-cli
> AUTH your-password

# أو في .env تأكد من:
REDIS_PASSWORD=your-password
```

---

## 📈 المراقبة والأداء

### 1. مراقبة Redis
```bash
redis-cli info stats
redis-cli info memory
```

### 2. عرض المفاتيح المحفوظة
```bash
redis-cli KEYS "idempotency:*"
```

### 3. فحص مفتاح معين
```bash
redis-cli GET "idempotency:abc123..."
redis-cli TTL "idempotency:abc123..."
```

### 4. حذف جميع مفاتيح Idempotency
```bash
redis-cli KEYS "idempotency:*" | xargs redis-cli DEL
```

---

## 🎯 أفضل الممارسات

### 1. اختيار TTL المناسب
- **قصير (1 ساعة)**: للبيئات التطويرية
- **متوسط (12 ساعة)**: للإنتاج العادي
- **طويل (24 ساعة)**: للحفاظ على النتائج لمدة أطول

### 2. مراقبة حجم الذاكرة
```bash
# تحقق من استخدام الذاكرة
redis-cli INFO memory | grep used_memory_human
```

### 3. عمل Backup دوري
```bash
# إعداد SAVE في redis.conf
save 900 1
save 300 10
save 60 10000
```

### 4. تفعيل Logging
تأكد من تفعيل logging في `app/logger.py` لمراقبة:
- Cache HITs/MISSes
- أخطاء Redis
- أوقات الاستجابة

---

## 🔐 الأمان

### 1. تأمين Redis في Production
```bash
# في redis.conf:
requirepass your-strong-password
bind 127.0.0.1 ::1  # فقط local connections
protected-mode yes

# أو في .env:
REDIS_PASSWORD=your-strong-password
REDIS_SSL=true
```

### 2. استخدام Firewall
```bash
# السماح فقط بـ local connections
sudo ufw allow from 127.0.0.1 to any port 6379
```

### 3. تشفير SSL/TLS
استخدم Redis Cloud أو قم بإعداد SSL:
```bash
REDIS_SSL=true
REDIS_PORT=6380
```

---

## 📞 الدعم

إذا واجهت أي مشاكل:
1. راجع logs في `logs/app.log`
2. تحقق من Redis logs: `redis-cli info all`
3. استخدم `/api/idempotency-stats` للحصول على إحصائيات

---

## ✅ Checklist قبل الإنتاج

- [ ] Redis يعمل ويمكن الاتصال به
- [ ] تم إعداد password قوي
- [ ] تم تفعيل SSL
- [ ] تم اختبار Idempotency
- [ ] تم إعداد monitoring
- [ ] تم إعداد backup
- [ ] تم اختبار failover
