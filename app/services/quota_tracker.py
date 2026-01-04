"""
Quota Tracker with MongoDB
Track and manage AI provider quotas
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.config import get_settings
from app.logger import app_logger
from app.services.mongodb_client import mongodb_client

settings = get_settings()


class QuotaTracker:
    """
    Track token usage and quota for AI providers
    """
    
    COLLECTION_NAME = "quota"
    
    def __init__(self):
        self.mongodb = mongodb_client
        
        # Quota limits (configurable per provider)
        self.limits = {
            'openai': {
                'daily_tokens': settings.max_daily_tokens,
                'daily_requests': settings.max_daily_requests,
                'hourly_tokens': settings.max_daily_tokens // 24,
                'hourly_requests': settings.max_daily_requests // 24
            },
            'gemini': {
                'daily_tokens': settings.max_daily_tokens,
                'daily_requests': settings.max_daily_requests,
                'hourly_tokens': settings.max_daily_tokens // 24,
                'hourly_requests': settings.max_daily_requests // 24
            }
        }
        
        # Warning thresholds (percentage)
        self.warning_threshold = 0.75  # 75%
        self.critical_threshold = 0.90  # 90%
    
    async def connect(self):
        """Initialize MongoDB connection"""
        await self.mongodb.connect()
        app_logger.info("✅ QuotaTracker connected to MongoDB")
    
    async def check_quota(self, provider: str, estimated_tokens: int) -> bool:
        """
        Check if provider has enough quota
        
        Args:
            provider: Provider name (openai, gemini)
            estimated_tokens: Estimated tokens for operation
        
        Returns:
            True if quota available, False otherwise
        """
        if not await self.mongodb.is_connected():
            await self.connect()
        
        # Get current usage
        daily_tokens = await self._get_usage(provider, 'daily', 'tokens')
        daily_requests = await self._get_usage(provider, 'daily', 'requests')
        hourly_tokens = await self._get_usage(provider, 'hourly', 'tokens')
        hourly_requests = await self._get_usage(provider, 'hourly', 'requests')
        
        # Get limits
        limits = self.limits.get(provider, {})
        
        # Check if we'd exceed any limit
        would_exceed_daily_tokens = (daily_tokens + estimated_tokens) > limits.get('daily_tokens', float('inf'))
        would_exceed_daily_requests = (daily_requests + 1) > limits.get('daily_requests', float('inf'))
        would_exceed_hourly_tokens = (hourly_tokens + estimated_tokens) > limits.get('hourly_tokens', float('inf'))
        would_exceed_hourly_requests = (hourly_requests + 1) > limits.get('hourly_requests', float('inf'))
        
        if would_exceed_daily_tokens or would_exceed_daily_requests:
            app_logger.warning(
                f"💳 Daily quota would be exceeded for {provider} - "
                f"Tokens: {daily_tokens}/{limits['daily_tokens']}, "
                f"Requests: {daily_requests}/{limits['daily_requests']}"
            )
            return False
        
        if would_exceed_hourly_tokens or would_exceed_hourly_requests:
            app_logger.warning(
                f"💳 Hourly quota would be exceeded for {provider} - "
                f"Tokens: {hourly_tokens}/{limits['hourly_tokens']}, "
                f"Requests: {hourly_requests}/{limits['hourly_requests']}"
            )
            return False
        
        # Check warning thresholds
        daily_usage_pct = daily_tokens / limits['daily_tokens']
        if daily_usage_pct >= self.critical_threshold:
            app_logger.error(f"🚨 CRITICAL: {provider} at {daily_usage_pct*100:.1f}% daily quota")
        elif daily_usage_pct >= self.warning_threshold:
            app_logger.warning(f"⚠️ WARNING: {provider} at {daily_usage_pct*100:.1f}% daily quota")
        
        return True
    
    async def increment_usage(
        self,
        provider: str,
        tokens_used: int,
        requests: int = 1
    ):
        """
        Increment usage counters
        
        Args:
            provider: Provider name
            tokens_used: Number of tokens used
            requests: Number of requests (default 1)
        """
        if not await self.mongodb.is_connected():
            await self.connect()
        
        now = datetime.utcnow()
        
        # Update daily counters
        await self._increment_counter(
            provider=provider,
            period_type='daily',
            period_key=now.strftime('%Y-%m-%d'),
            tokens=tokens_used,
            requests=requests,
            expires_in_seconds=86400 * 2  # 2 days
        )
        
        # Update hourly counters
        await self._increment_counter(
            provider=provider,
            period_type='hourly',
            period_key=now.strftime('%Y-%m-%d:%H'),
            tokens=tokens_used,
            requests=requests,
            expires_in_seconds=7200  # 2 hours
        )
        
        app_logger.debug(f"📊 Quota updated for {provider}: +{tokens_used} tokens, +{requests} requests")
    
    async def _increment_counter(
        self,
        provider: str,
        period_type: str,
        period_key: str,
        tokens: int,
        requests: int,
        expires_in_seconds: int
    ):
        """
        Increment usage counter in MongoDB
        """
        try:
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
            
            # Use $inc to atomically increment counters
            await collection.update_one(
                {
                    "provider": provider,
                    "period_type": period_type,
                    "period_key": period_key
                },
                {
                    "$inc": {
                        "tokens": tokens,
                        "requests": requests
                    },
                    "$set": {
                        "expires_at": expires_at,
                        "last_updated": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
        except Exception as e:
            app_logger.error(f"Error incrementing counter: {str(e)}")
    
    async def _get_usage(self, provider: str, period: str, metric: str) -> int:
        """
        Get current usage
        
        Args:
            provider: Provider name
            period: 'daily' or 'hourly'
            metric: 'tokens' or 'requests'
        
        Returns:
            Current usage count
        """
        try:
            now = datetime.utcnow()
            
            if period == 'daily':
                period_key = now.strftime('%Y-%m-%d')
            else:  # hourly
                period_key = now.strftime('%Y-%m-%d:%H')
            
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            document = await collection.find_one({
                "provider": provider,
                "period_type": period,
                "period_key": period_key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if document:
                return document.get(metric, 0)
            
            return 0
            
        except Exception as e:
            app_logger.error(f"Error getting usage: {str(e)}")
            return 0
    
    async def get_usage_stats(self, provider: str) -> Dict:
        """
        Get comprehensive usage statistics
        
        Args:
            provider: Provider name
        
        Returns:
            Dictionary with usage stats
        """
        daily_tokens = await self._get_usage(provider, 'daily', 'tokens')
        daily_requests = await self._get_usage(provider, 'daily', 'requests')
        hourly_tokens = await self._get_usage(provider, 'hourly', 'tokens')
        hourly_requests = await self._get_usage(provider, 'hourly', 'requests')
        
        limits = self.limits.get(provider, {})
        
        return {
            'provider': provider,
            'daily': {
                'tokens': {
                    'used': daily_tokens,
                    'limit': limits.get('daily_tokens', 0),
                    'remaining': max(0, limits.get('daily_tokens', 0) - daily_tokens),
                    'percentage': (daily_tokens / limits.get('daily_tokens', 1)) * 100
                },
                'requests': {
                    'used': daily_requests,
                    'limit': limits.get('daily_requests', 0),
                    'remaining': max(0, limits.get('daily_requests', 0) - daily_requests),
                    'percentage': (daily_requests / limits.get('daily_requests', 1)) * 100
                }
            },
            'hourly': {
                'tokens': {
                    'used': hourly_tokens,
                    'limit': limits.get('hourly_tokens', 0),
                    'remaining': max(0, limits.get('hourly_tokens', 0) - hourly_tokens),
                    'percentage': (hourly_tokens / limits.get('hourly_tokens', 1)) * 100
                },
                'requests': {
                    'used': hourly_requests,
                    'limit': limits.get('hourly_requests', 0),
                    'remaining': max(0, limits.get('hourly_requests', 0) - hourly_requests),
                    'percentage': (hourly_requests / limits.get('hourly_requests', 1)) * 100
                }
            }
        }
    
    async def reset_quota(self, provider: str):
        """
        Reset quota counters (admin function)
        """
        if not await self.mongodb.is_connected():
            await self.connect()
        
        try:
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)
            
            # Delete all documents for this provider
            result = await collection.delete_many({"provider": provider})
            
            app_logger.info(f"🔄 Quota reset for {provider} - Deleted {result.deleted_count} documents")
            
        except Exception as e:
            app_logger.error(f"Error resetting quota: {str(e)}")
    
    async def get_all_providers_stats(self) -> Dict:
        """
        Get stats for all providers
        """
        stats = {}
        for provider in ['openai', 'gemini']:
            stats[provider] = await self.get_usage_stats(provider)
        
        return stats
    
    async def predict_exhaustion(self, provider: str) -> Optional[datetime]:
        """
        Predict when quota will be exhausted based on current usage rate
        
        Returns:
            Estimated datetime when quota will run out, or None if usage is low
        """
        stats = await self.get_usage_stats(provider)
        
        daily_tokens_used = stats['daily']['tokens']['used']
        daily_tokens_limit = stats['daily']['tokens']['limit']
        
        if daily_tokens_used == 0:
            return None
        
        # Calculate usage rate (tokens per hour)
        now = datetime.utcnow()
        hours_elapsed = now.hour + (now.minute / 60)
        
        if hours_elapsed == 0:
            return None
        
        tokens_per_hour = daily_tokens_used / hours_elapsed
        remaining_tokens = daily_tokens_limit - daily_tokens_used
        
        if remaining_tokens <= 0:
            return now  # Already exhausted
        
        hours_until_exhaustion = remaining_tokens / tokens_per_hour
        exhaustion_time = now + timedelta(hours=hours_until_exhaustion)
        
        # Only return if exhaustion is within next 24 hours
        if hours_until_exhaustion < 24:
            app_logger.warning(
                f"📉 {provider} quota predicted to exhaust at {exhaustion_time.strftime('%H:%M')}"
            )
            return exhaustion_time
        
        return None


# Global instance
quota_tracker = QuotaTracker()