import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from app.config import get_settings
from app.logger import app_logger

settings = get_settings()

class GracefulDegradationService:
    """
    Service for managing AI response caching and fallback.
    Ensures business continuity when live AI providers fail by serving
    historically successful analyses for similar inputs.
    """
    
    def __init__(self):
        self.settings = settings
        self.logger = app_logger
        self.redis_client: Optional[redis.Redis] = None
        # Default to 7 days if not specified in settings
        self.ttl = getattr(settings, 'graceful_degradation_ttl', 60 * 60 * 24 * 7)
        self.enabled = getattr(settings, 'graceful_degradation_enable', True)
        
    async def connect(self):
        """Create Redis connection"""
        if not self.enabled:
            self.logger.info("Graceful Degradation is disabled")
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
            
            # Test connection
            await self.redis_client.ping()
            self.logger.info("✅ Redis connected successfully for Graceful Degradation")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Redis (Graceful Degradation): {str(e)}")
            self.redis_client = None
            # We don't raise here to allow the app to start without fallback capability
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Graceful Degradation Redis connection closed")

    def _generate_content_hash(self, text: str) -> str:
        """
        Generate deterministic hash for policy content.
        """
        if not text:
            return "empty"
        # Normalize and hash
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def _get_cache_key(self, policy_type: str, content_hash: str) -> str:
        """Format the Redis key"""
        return f"graceful_fallback:{policy_type}:{content_hash}"

    async def get_cached_similar_result(
        self, 
        policy_text: str, 
        policy_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a previously successful analysis for the same content.
        """
        if not self.enabled or not self.redis_client or not policy_text:
            return None

        try:
            content_hash = self._generate_content_hash(policy_text)
            key = self._get_cache_key(policy_type, content_hash)
            
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                self.logger.info(f"✨ Graceful Degradation: Cache HIT for {policy_type}")
                result = json.loads(cached_data)
                
                # Add metadata indicating source
                result['from_cache'] = True
                result['graceful_degradation'] = True
                result['retrieved_at'] = datetime.now().isoformat()
                
                return result
                
            self.logger.debug(f"Graceful Degradation: Cache MISS for {policy_type}")
            return None

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in graceful degradation: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving fallback result: {str(e)}")
            return None

    async def cache_successful_result(
        self, 
        policy_text: str, 
        policy_type: str, 
        result: Dict[str, Any]
    ) -> bool:
        """
        Store successful AI results for future fallback usage.
        """
        if not self.enabled or not self.redis_client or not result:
            return False

        try:
            content_hash = self._generate_content_hash(policy_text)
            key = self._get_cache_key(policy_type, content_hash)
            
            # Clean result metadata before caching
            cache_payload = result.copy()
            cache_payload['cached_at'] = datetime.now().isoformat()
            
            # Remove transient fields if they exist
            cache_payload.pop('from_cache', None)
            cache_payload.pop('graceful_degradation', None)
            
            await self.redis_client.setex(
                key,
                self.ttl,
                json.dumps(cache_payload, ensure_ascii=False)
            )
            
            self.logger.debug(f"💾 Result cached for fallback: {key[:30]}...")
            return True

        except Exception as e:
            self.logger.error(f"Error caching result for fallback: {str(e)}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get service health stats
        """
        if not self.enabled or not self.redis_client:
            return {"enabled": self.enabled, "connected": False}
            
        try:
            # Count keys matching our prefix
            # Note: KEYS is expensive, in production use SCAN or just return connected status
            return {
                "enabled": True,
                "connected": True,
                "ttl_setting": self.ttl
            }
        except Exception as e:
            return {"error": str(e)}

# Singleton instance
graceful_degradation_service = GracefulDegradationService()