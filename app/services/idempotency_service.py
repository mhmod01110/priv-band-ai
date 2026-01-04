"""
Idempotency Service with MongoDB
Prevents duplicate requests and caches results
"""
import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.config import get_settings
from app.logger import app_logger
from app.services.mongodb_client import mongodb_client

settings = get_settings()


class IdempotencyService:
    """
    خدمة إدارة Idempotency Keys مع MongoDB
    تمنع تكرار الطلبات وتحفظ النتائج لمدة محددة
    """
    
    COLLECTION_NAME = "idempotency"
    
    def __init__(self):
        self.settings = settings
        self.logger = app_logger
        self.mongodb = mongodb_client
        self.ttl = settings.idempotency_ttl
        self.enabled = settings.idempotency_enable
        
    async def connect(self):
        """إنشاء اتصال مع MongoDB"""
        if not self.enabled:
            self.logger.info("Idempotency is disabled")
            return
            
        try:
            await self.mongodb.connect()
            self.logger.info("✅ Idempotency service connected to MongoDB")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect idempotency service: {str(e)}")
            raise
    
    async def disconnect(self):
        """إغلاق اتصال MongoDB"""
        # MongoDB client handles disconnection centrally
        pass
    
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
        if not self.enabled or not await self.mongodb.is_connected():
            return None
            
        try:
            key = self._normalize_key(idempotency_key)
            
            # Get from MongoDB
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            document = await collection.find_one({
                "key": key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if document:
                self.logger.info(f"✅ Cache HIT for key: {key[:20]}...")
                
                result = document.get("value")
                
                # إضافة معلومة أن النتيجة من الـ cache
                if isinstance(result, dict):
                    result["from_cache"] = True
                    result["cache_timestamp"] = document.get("created_at", "").isoformat() if document.get("created_at") else ""
                
                return result
            
            self.logger.debug(f"Cache MISS for key: {key[:20]}...")
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
        حفظ نتيجة في MongoDB مع idempotency key
        """
        if not self.enabled or not await self.mongodb.is_connected():
            return False
            
        try:
            key = self._normalize_key(idempotency_key)
            ttl = ttl_override or self.ttl
            
            # إضافة timestamp
            result_copy = result.copy()
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            document = {
                "key": key,
                "value": result_copy,
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                "ttl": ttl
            }
            
            await collection.update_one(
                {"key": key},
                {"$set": document},
                upsert=True
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
        if not self.enabled or not await self.mongodb.is_connected():
            return False
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            count = await collection.count_documents({
                "key": lock_key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return count > 0
            
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
        if not self.enabled or not await self.mongodb.is_connected():
            return True
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            # Check if lock already exists
            existing = await collection.find_one({
                "key": lock_key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if existing:
                self.logger.warning(f"Lock already exists for key: {lock_key[:30]}...")
                return False
            
            # Create lock
            expires_at = datetime.utcnow() + timedelta(seconds=timeout)
            
            document = {
                "key": lock_key,
                "value": datetime.utcnow().isoformat(),
                "expires_at": expires_at,
                "created_at": datetime.utcnow()
            }
            
            await collection.insert_one(document)
            
            self.logger.debug(f"Lock acquired for key: {lock_key[:30]}...")
            return True
                
        except Exception as e:
            self.logger.error(f"Error marking in-progress: {str(e)}")
            return False
    
    async def clear_in_progress(self, idempotency_key: str):
        """
        إزالة علامة التنفيذ (unlock)
        """
        if not self.enabled or not await self.mongodb.is_connected():
            return
            
        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            await collection.delete_one({"key": lock_key})
            
            self.logger.debug(f"Lock released for key: {lock_key[:30]}...")
            
        except Exception as e:
            self.logger.error(f"Error clearing in-progress: {str(e)}")
    
    async def delete_cached_result(self, idempotency_key: str) -> bool:
        """
        حذف نتيجة محفوظة (للحالات الخاصة)
        """
        if not self.enabled or not await self.mongodb.is_connected():
            return False
            
        try:
            key = self._normalize_key(idempotency_key)
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            result = await collection.delete_one({"key": key})
            
            if result.deleted_count > 0:
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
        if not self.enabled or not await self.mongodb.is_connected():
            return {"enabled": False}
            
        try:
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            total_keys = await collection.count_documents({})
            active_keys = await collection.count_documents({
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return {
                "enabled": True,
                "total_keys": total_keys,
                "active_keys": active_keys,
                "expired_keys": total_keys - active_keys,
                "connected": True
            }
        except Exception as e:
            self.logger.error(f"Error getting stats: {str(e)}")
            return {"enabled": True, "connected": False, "error": str(e)}


# Singleton instance
idempotency_service = IdempotencyService()