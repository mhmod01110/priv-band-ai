"""
Multi-Provider Manager
Intelligent routing and fallback between OpenAI and Gemini
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, Literal
from enum import Enum

from app.services.openai import OpenAIService
from app.services.gemini import GeminiService
from app.services.quota_tracker import QuotaTracker
from app.services.error_handler import AIErrorHandler, ErrorType
from app.services.graceful_degradation import graceful_degradation_service
from app.logger import app_logger
from app.config import get_settings

settings = get_settings()


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLACKLISTED = "blacklisted"
    QUOTA_EXCEEDED = "quota_exceeded"


class ProviderManager:
    """
    Manages multiple AI providers with intelligent failover
    """
    
    def __init__(self, primary_provider: str = None):
        self.primary = primary_provider or settings.ai_provider
        self.secondary = 'gemini' if self.primary == 'openai' else 'openai'
        
        # Initialize services
        self.providers = {
            'openai': OpenAIService(),
            'gemini': GeminiService()
        }
        
        # Health tracking
        self.health_status: Dict[str, Dict[str, Any]] = {
            'openai': {
                'status': ProviderStatus.HEALTHY,
                'last_error': None,
                'last_success': datetime.utcnow(),
                'blacklist_until': None,
                'error_count': 0,
                'total_requests': 0,
                'successful_requests': 0
            },
            'gemini': {
                'status': ProviderStatus.HEALTHY,
                'last_error': None,
                'last_success': datetime.utcnow(),
                'blacklist_until': None,
                'error_count': 0,
                'total_requests': 0,
                'successful_requests': 0
            }
        }
        
        # Dependencies
        self.quota_tracker = QuotaTracker()
        self.error_handler = AIErrorHandler()
        
        # Configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.blacklist_duration = 300  # 5 minutes
        self.failover_count = 0
        
        app_logger.info(f"🎯 ProviderManager initialized - Primary: {self.primary}, Secondary: {self.secondary}")
    
    async def execute_with_fallback(
        self,
        operation: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute operation with automatic fallback
        
        Args:
            operation: Method name to call (e.g., 'check_policy_match', 'analyze_compliance')
            *args, **kwargs: Arguments to pass to the method
        
        Returns:
            Result from AI provider
        """
        app_logger.info(f"🚀 Executing '{operation}' with fallback strategy")
        
        # Try primary provider
        try:
            result = await self._execute_with_provider(
                self.primary,
                operation,
                *args,
                **kwargs
            )
            app_logger.info(f"✅ Primary provider ({self.primary}) succeeded")
            return result
            
        except Exception as primary_error:
            app_logger.warning(f"⚠️ Primary provider ({self.primary}) failed: {str(primary_error)}")
            
            # Classify error
            error_type = self.error_handler.classify_error(primary_error)
            app_logger.info(f"📊 Error classified as: {error_type}")
            
            # Handle based on error type
            if error_type == ErrorType.QUOTA_EXCEEDED:
                app_logger.warning(f"💳 Quota exceeded for {self.primary}")
                self._mark_quota_exceeded(self.primary)
            
            elif error_type == ErrorType.SERVICE_CRASH:
                app_logger.error(f"💥 Service crash detected for {self.primary}")
                self._blacklist_provider(self.primary, duration=self.blacklist_duration)
            
            elif error_type == ErrorType.TIMEOUT:
                app_logger.warning(f"⏱️ Timeout for {self.primary}")
                # Don't blacklist for timeout, just retry
            
            # Try secondary provider
            try:
                self.failover_count += 1
                app_logger.info(f"🔄 Failing over to secondary provider ({self.secondary}) - Count: {self.failover_count}")
                
                result = await self._execute_with_provider(
                    self.secondary,
                    operation,
                    *args,
                    **kwargs
                )
                app_logger.info(f"✅ Secondary provider ({self.secondary}) succeeded")
                return result
                
            except Exception as secondary_error:
                app_logger.error(f"❌ Secondary provider ({self.secondary}) also failed: {str(secondary_error)}")
                
                # Both providers failed - try graceful degradation
                return await self._graceful_degradation(
                    operation,
                    primary_error,
                    secondary_error,
                    *args,
                    **kwargs
                )
    
    async def _execute_with_provider(
        self,
        provider: str,
        operation: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute operation with specific provider
        """
        # Check if provider is blacklisted
        if self._is_blacklisted(provider):
            remaining = self._get_blacklist_remaining(provider)
            raise Exception(f"Provider {provider} is blacklisted for {remaining} seconds")
        
        # Check quota before executing
        await self._check_quota(provider, operation)
        
        # Get provider service
        service = self.providers[provider]
        
        # Track request
        self.health_status[provider]['total_requests'] += 1
        
        try:
            # Execute with retries
            for attempt in range(self.max_retries):
                try:
                    # Call the appropriate method
                    if operation == 'check_policy_match':
                        result = await service.check_policy_match(*args, **kwargs)
                    elif operation == 'analyze_compliance':
                        result = await service.analyze_compliance(*args, **kwargs)
                    elif operation == 'regenerate_policy':
                        result = await service.regenerate_policy(*args, **kwargs)
                    else:
                        raise ValueError(f"Unknown operation: {operation}")
                    
                    # Success - update health status
                    self._record_success(provider)
                    return result
                    
                except Exception as e:
                    app_logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for {provider}: {str(e)}")
                    
                    # Check if we should retry
                    error_type = self.error_handler.classify_error(e)
                    if not self.error_handler.should_retry(error_type):
                        raise
                    
                    # Wait before retry
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
        
        except Exception as e:
            # Record failure
            self._record_failure(provider, e)
            raise
    
    async def _check_quota(self, provider: str, operation: str):
        """
        Check if provider has enough quota
        """
        # Estimate tokens needed
        estimated_tokens = self._estimate_tokens(operation)
        
        # Check quota
        has_quota = await self.quota_tracker.check_quota(provider, estimated_tokens)
        
        if not has_quota:
            self._mark_quota_exceeded(provider)
            raise Exception(f"Quota exhausted for {provider}")
    
    def _estimate_tokens(self, operation: str) -> int:
        """
        Estimate tokens needed for operation
        """
        estimates = {
            'check_policy_match': 2000,  # Light model
            'analyze_compliance': 10000,  # Heavy model
            'regenerate_policy': 12000   # Heavy model
        }
        return estimates.get(operation, 5000)
    
    def _is_blacklisted(self, provider: str) -> bool:
        """
        Check if provider is currently blacklisted
        """
        status = self.health_status[provider]
        
        if status['blacklist_until'] is None:
            return False
        
        # Check if blacklist expired
        if datetime.utcnow() >= status['blacklist_until']:
            # Unblacklist
            status['blacklist_until'] = None
            status['status'] = ProviderStatus.HEALTHY
            status['error_count'] = 0
            app_logger.info(f"✅ Provider {provider} unblacklisted")
            return False
        
        return True
    
    def _get_blacklist_remaining(self, provider: str) -> int:
        """
        Get remaining blacklist time in seconds
        """
        blacklist_until = self.health_status[provider]['blacklist_until']
        if blacklist_until is None:
            return 0
        
        remaining = (blacklist_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    def _blacklist_provider(self, provider: str, duration: int):
        """
        Temporarily blacklist a provider
        """
        self.health_status[provider]['status'] = ProviderStatus.BLACKLISTED
        self.health_status[provider]['blacklist_until'] = datetime.utcnow() + timedelta(seconds=duration)
        
        app_logger.warning(f"🚫 Provider {provider} blacklisted for {duration} seconds")
    
    def _mark_quota_exceeded(self, provider: str):
        """
        Mark provider as quota exceeded
        """
        self.health_status[provider]['status'] = ProviderStatus.QUOTA_EXCEEDED
        app_logger.warning(f"💳 Provider {provider} marked as quota exceeded")
    
    def _record_success(self, provider: str):
        """
        Record successful request
        """
        self.health_status[provider]['successful_requests'] += 1
        self.health_status[provider]['last_success'] = datetime.utcnow()
        self.health_status[provider]['error_count'] = 0
        
        # Update status if was degraded
        if self.health_status[provider]['status'] != ProviderStatus.HEALTHY:
            self.health_status[provider]['status'] = ProviderStatus.HEALTHY
            app_logger.info(f"✅ Provider {provider} recovered to healthy")
    
    def _record_failure(self, provider: str, error: Exception):
        """
        Record failed request
        """
        self.health_status[provider]['error_count'] += 1
        self.health_status[provider]['last_error'] = str(error)
        
        # Mark as degraded if too many errors
        if self.health_status[provider]['error_count'] >= 3:
            self.health_status[provider]['status'] = ProviderStatus.DEGRADED
            app_logger.warning(f"⚠️ Provider {provider} marked as degraded")
    
    async def _graceful_degradation(
        self,
        operation: str,
        primary_error: Exception,
        secondary_error: Exception,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle case when both providers failed
        """
        app_logger.error("❌ Both providers failed - attempting graceful degradation")
        
        # Try to return cached result
        if 'policy_text' in kwargs and 'policy_type' in kwargs:
            from app.services.graceful_degradation import graceful_degradation_service
            
            cached = await graceful_degradation_service.get_cached_similar_result(
                kwargs.get('policy_text'),
                kwargs.get('policy_type')
            )
            
            if cached:
                app_logger.info("✅ Returning cached similar result")
                cached['from_cache'] = True
                cached['graceful_degradation'] = True
                return cached
        
        # Return rule-based fallback for stage 1
        if operation == 'check_policy_match':
            from app.utils.policy_validator import rule_based_policy_match
            
            result = rule_based_policy_match(
                kwargs.get('policy_type'),
                kwargs.get('policy_text')
            )
            result['graceful_degradation'] = True
            result['note'] = 'تم التحليل بناءً على قواعد محلية نظراً لعدم توفر خدمات الذكاء الاصطناعي مؤقتاً'
            return result
        
        # For other operations, raise error with helpful message
        raise Exception(
            f"جميع خدمات الذكاء الاصطناعي غير متوفرة حالياً. "
            f"الأخطاء: {str(primary_error)}, {str(secondary_error)}"
        )
    
    def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive health report
        """
        report = {
            'primary_provider': self.primary,
            'secondary_provider': self.secondary,
            'failover_count': self.failover_count,
            'providers': {}
        }
        
        for provider, status in self.health_status.items():
            success_rate = 0
            if status['total_requests'] > 0:
                success_rate = (status['successful_requests'] / status['total_requests']) * 100
            
            report['providers'][provider] = {
                'status': status['status'],
                'success_rate': round(success_rate, 2),
                'total_requests': status['total_requests'],
                'error_count': status['error_count'],
                'last_success': status['last_success'].isoformat() if status['last_success'] else None,
                'last_error': status['last_error'],
                'blacklisted': self._is_blacklisted(provider),
                'blacklist_remaining': self._get_blacklist_remaining(provider) if self._is_blacklisted(provider) else 0
            }
        
        return report
    
    async def switch_primary_provider(self, new_primary: str):
        """
        Manually switch primary provider
        """
        if new_primary not in self.providers:
            raise ValueError(f"Unknown provider: {new_primary}")
        
        old_primary = self.primary
        self.primary = new_primary
        self.secondary = 'gemini' if new_primary == 'openai' else 'openai'
        
        app_logger.info(f"🔄 Primary provider switched: {old_primary} → {new_primary}")


# Global instance
provider_manager = ProviderManager()