"""
Graceful Degradation Service with MongoDB
Caching successful AI responses for fallback
"""
import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.config import get_settings
from app.logger import app_logger
from app.services.mongodb_client import mongodb_client

settings = get_settings()


class GracefulDegradationService:
    """
    Service for managing AI response caching and fallback.
    Ensures business continuity when live AI providers fail by serving
    historically successful analyses for similar inputs.
    """
    
    COLLECTION_NAME = "graceful_fallback"
    
    def __init__(self):
        self.settings = settings
        self.logger = app_logger
        self.mongodb = mongodb_client
        # Default to 7 days if not specified in settings
        self.ttl = getattr(settings, 'graceful_degradation_ttl', 60 * 60 * 24 * 7)
        self.enabled = getattr(settings, 'graceful_degradation_enable', True)
        
    async def connect(self):
        """Create MongoDB connection"""
        if not self.enabled:
            self.logger.info("Graceful Degradation is disabled")
            return
            
        try:
            await self.mongodb.connect()
            self.logger.info("✅ Graceful Degradation service connected to MongoDB")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect Graceful Degradation service: {str(e)}")
            # We don't raise here to allow the app to start without fallback capability
    
    async def disconnect(self):
        """Close MongoDB connection"""
        # MongoDB client handles disconnection centrally
        pass

    def _generate_content_hash(self, text: str) -> str:
        """
        Generate deterministic hash for policy content.
        """
        if not text:
            return "empty"
        # Normalize and hash
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def _get_cache_key(self, policy_type: str, content_hash: str) -> str:
        """Format the cache key"""
        return f"graceful_fallback:{policy_type}:{content_hash}"

    async def get_cached_similar_result(
        self, 
        policy_text: str, 
        policy_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a previously successful analysis for the same content.
        """
        if not self.enabled or not await self.mongodb.is_connected() or not policy_text:
            return None

        try:
            content_hash = self._generate_content_hash(policy_text)
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            # Find document
            document = await collection.find_one({
                "policy_type": policy_type,
                "content_hash": content_hash,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if document:
                self.logger.info(f"✨ Graceful Degradation: Cache HIT for {policy_type}")
                
                result = document.get("result")
                
                # Add metadata indicating source
                if isinstance(result, dict):
                    result['from_cache'] = True
                    result['graceful_degradation'] = True
                    result['retrieved_at'] = datetime.utcnow().isoformat()
                
                return result
                
            self.logger.debug(f"Graceful Degradation: Cache MISS for {policy_type}")
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
        if not self.enabled or not await self.mongodb.is_connected() or not result:
            return False

        try:
            content_hash = self._generate_content_hash(policy_text)
            
            # Clean result metadata before caching
            cache_payload = result.copy()
            
            # Remove transient fields if they exist
            cache_payload.pop('from_cache', None)
            cache_payload.pop('graceful_degradation', None)
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            expires_at = datetime.utcnow() + timedelta(seconds=self.ttl)
            
            document = {
                "policy_type": policy_type,
                "content_hash": content_hash,
                "result": cache_payload,
                "expires_at": expires_at,
                "cached_at": datetime.utcnow(),
                "ttl": self.ttl
            }
            
            await collection.update_one(
                {"policy_type": policy_type, "content_hash": content_hash},
                {"$set": document},
                upsert=True
            )
            
            self.logger.debug(f"💾 Result cached for fallback: {policy_type}/{content_hash[:10]}...")
            return True

        except Exception as e:
            self.logger.error(f"Error caching result for fallback: {str(e)}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get service health stats
        """
        if not self.enabled or not await self.mongodb.is_connected():
            return {"enabled": self.enabled, "connected": False}
            
        try:
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            total_count = await collection.count_documents({})
            active_count = await collection.count_documents({
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return {
                "enabled": True,
                "connected": True,
                "total_cached": total_count,
                "active_cached": active_count,
                "ttl_setting": self.ttl
            }
        except Exception as e:
            return {"error": str(e)}


# Singleton instance
graceful_degradation_service = GracefulDegradationService()