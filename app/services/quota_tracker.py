"""
Quota Tracker
Track and manage AI provider quotas
"""
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.config import get_settings
from app.logger import app_logger

settings = get_settings()


class QuotaTracker:
    """
    Track token usage and quota for AI providers
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        
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
        """Initialize Redis connection"""
        if not self.redis_client:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password if settings.redis_password else None,
                decode_responses=True
            )
            await self.redis_client.ping()
            app_logger.info("✅ QuotaTracker connected to Redis")
    
    async def check_quota(self, provider: str, estimated_tokens: int) -> bool:
        """
        Check if provider has enough quota
        
        Args:
            provider: Provider name (openai, gemini)
            estimated_tokens: Estimated tokens for operation
        
        Returns:
            True if quota available, False otherwise
        """
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
        await self.connect()
        
        now = datetime.utcnow()
        
        # Daily keys
        daily_key_prefix = f"quota:{provider}:daily:{now.strftime('%Y-%m-%d')}"
        await self.redis_client.incrby(f"{daily_key_prefix}:tokens", tokens_used)
        await self.redis_client.incrby(f"{daily_key_prefix}:requests", requests)
        await self.redis_client.expire(f"{daily_key_prefix}:tokens", 86400 * 2)  # 2 days
        await self.redis_client.expire(f"{daily_key_prefix}:requests", 86400 * 2)
        
        # Hourly keys
        hourly_key_prefix = f"quota:{provider}:hourly:{now.strftime('%Y-%m-%d:%H')}"
        await self.redis_client.incrby(f"{hourly_key_prefix}:tokens", tokens_used)
        await self.redis_client.incrby(f"{hourly_key_prefix}:requests", requests)
        await self.redis_client.expire(f"{hourly_key_prefix}:tokens", 7200)  # 2 hours
        await self.redis_client.expire(f"{hourly_key_prefix}:requests", 7200)
        
        app_logger.debug(f"📊 Quota updated for {provider}: +{tokens_used} tokens, +{requests} requests")
    
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
        now = datetime.utcnow()
        
        if period == 'daily':
            key = f"quota:{provider}:daily:{now.strftime('%Y-%m-%d')}:{metric}"
        else:  # hourly
            key = f"quota:{provider}:hourly:{now.strftime('%Y-%m-%d:%H')}:{metric}"
        
        value = await self.redis_client.get(key)
        return int(value) if value else 0
    
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
        await self.connect()
        
        now = datetime.utcnow()
        
        # Delete daily and hourly keys
        daily_pattern = f"quota:{provider}:daily:*"
        hourly_pattern = f"quota:{provider}:hourly:*"
        
        # Note: In production, use SCAN for large keyspaces
        daily_keys = await self.redis_client.keys(daily_pattern)
        hourly_keys = await self.redis_client.keys(hourly_pattern)
        
        if daily_keys:
            await self.redis_client.delete(*daily_keys)
        if hourly_keys:
            await self.redis_client.delete(*hourly_keys)
        
        app_logger.info(f"🔄 Quota reset for {provider}")
    
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