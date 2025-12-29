import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from app.config import get_settings
from app.logger import app_logger

settings = get_settings()

class IdempotencyService:
    """
    خدمة إدارة Idempotency Keys مع Redis
    تمنع تكرار الطلبات وتحفظ النتائج لمدة محددة
    """
    
    def __init__(self):
        self.settings = settings
        self.logger = app_logger
        self.redis_client: Optional[redis.Redis] = None
        self.ttl = settings.idempotency_ttl
        self.enabled = settings.idempotency_enable
        
    async def connect(self):
        """إنشاء اتصال مع Redis"""
        if not self.enabled:
            self.logger.info("Idempotency is disabled")
            return
            
        try:
            self.redis_client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password if self.settings.redis_password else None,
                ssl=self.settings.redis_ssl,
                decode_responses=self.settings.redis_decode_responses,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            
            # اختبار الاتصال
            await self.redis_client.ping()
            self.logger.info("✅ Redis connected successfully for idempotency")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Redis: {str(e)}")
            self.redis_client = None
            raise
    
    async def disconnect(self):
        """إغلاق اتصال Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Redis connection closed")
    
    def generate_key_from_request(self, request_data: Dict[str, Any]) -> str:
        """
        توليد idempotency key من بيانات الطلب
        يستخدم hash للحفاظ على الخصوصية وتقليل حجم المفتاح
        """
        # إنشاء representation قابل للتكرار
        key_data = {
            "shop_name": request_data.get("shop_name", ""),
            "shop_specialization": request_data.get("shop_specialization", ""),
            "policy_type": request_data.get("policy_type", ""),
            # استخدام أول 2000 حرف فقط للمقارنة
            "policy_text_hash": hashlib.sha256(
                request_data.get("policy_text", "").encode()
            ).hexdigest()
        }
        
        # تحويل إلى JSON وحساب SHA256
        json_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        key_hash = hashlib.sha256(json_str.encode()).hexdigest()
        
        return f"idempotency:{key_hash}"
    
    async def get_cached_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        استرجاع نتيجة محفوظة باستخدام idempotency key
        """
        if not self.enabled or not self.redis_client:
            return None
            
        try:
            key = self._normalize_key(idempotency_key)
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                self.logger.info(f"✅ Cache HIT for key: {key[:20]}...")
                result = json.loads(cached_data)
                
                # إضافة معلومة أن النتيجة من الـ cache
                result["from_cache"] = True
                result["cache_timestamp"] = result.get("timestamp", "")
                
                return result
            
            self.logger.debug(f"Cache MISS for key: {key[:20]}...")
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error from cache: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting cached result: {str(e)}")
            return None
    
    async def store_result(
        self, 
        idempotency_key: str, 
        result: Dict[str, Any],
        ttl_override: Optional[int] = None
    ) -> bool:
        """
        حفظ نتيجة في Redis مع idempotency key
        """
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            key = self._normalize_key(idempotency_key)
            ttl = ttl_override or self.ttl
            
            # إضافة timestamp
            result["timestamp"] = datetime.now().isoformat()
            result["ttl"] = ttl
            
            # حفظ في Redis
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(result, ensure_ascii=False)
            )
            
            self.logger.info(
                f"✅ Result cached with key: {key[:20]}... (TTL: {ttl}s)"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing result in cache: {str(e)}")
            return False
    
    async def check_in_progress(self, idempotency_key: str) -> bool:
        """
        التحقق من وجود طلب قيد التنفيذ بنفس المفتاح
        """
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            exists = await self.redis_client.exists(lock_key)
            return bool(exists)
            
        except Exception as e:
            self.logger.error(f"Error checking in-progress: {str(e)}")
            return False
    
    async def mark_in_progress(
        self, 
        idempotency_key: str,
        timeout: int = 300
    ) -> bool:
        """
        وضع علامة أن الطلب قيد التنفيذ (lock)
        """
        if not self.enabled or not self.redis_client:
            return True
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            
            # استخدام SET NX (set if not exists) مع expiry
            was_set = await self.redis_client.set(
                lock_key,
                datetime.now().isoformat(),
                nx=True,  # فقط إذا لم يكن موجود
                ex=timeout  # ينتهي بعد timeout ثانية
            )
            
            if was_set:
                self.logger.debug(f"Lock acquired for key: {lock_key[:30]}...")
                return True
            else:
                self.logger.warning(f"Lock already exists for key: {lock_key[:30]}...")
                return False
                
        except Exception as e:
            self.logger.error(f"Error marking in-progress: {str(e)}")
            return False
    
    async def clear_in_progress(self, idempotency_key: str):
        """
        إزالة علامة التنفيذ (unlock)
        """
        if not self.enabled or not self.redis_client:
            return
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            await self.redis_client.delete(lock_key)
            self.logger.debug(f"Lock released for key: {lock_key[:30]}...")
            
        except Exception as e:
            self.logger.error(f"Error clearing in-progress: {str(e)}")
    
    async def delete_cached_result(self, idempotency_key: str) -> bool:
        """
        حذف نتيجة محفوظة (للحالات الخاصة)
        """
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            key = self._normalize_key(idempotency_key)
            deleted = await self.redis_client.delete(key)
            
            if deleted:
                self.logger.info(f"Deleted cached result for key: {key[:20]}...")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting cached result: {str(e)}")
            return False
    
    def _normalize_key(self, key: str) -> str:
        """
        تنظيم المفتاح (إضافة prefix إذا لم يكن موجود)
        """
        if not key.startswith("idempotency:"):
            return f"idempotency:{key}"
        return key
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        إحصائيات عن الـ cache
        """
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
            
        try:
            info = await self.redis_client.info("stats")
            keys_count = await self.redis_client.dbsize()
            
            return {
                "enabled": True,
                "total_keys": keys_count,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "connected": True
            }
        except Exception as e:
            self.logger.error(f"Error getting stats: {str(e)}")
            return {"enabled": True, "connected": False, "error": str(e)}


# Singleton instance
idempotency_service = IdempotencyService()
