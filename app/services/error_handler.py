"""
AI Error Handler
Classify and handle AI provider errors intelligently
"""
from enum import Enum
from typing import Optional, Dict, Any
import re
from app.logger import app_logger


class ErrorType(str, Enum):
    """Error classification"""
    QUOTA_EXCEEDED = "quota_exceeded"
    SERVICE_CRASH = "service_crash"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION = "authentication"
    NETWORK = "network"
    UNKNOWN = "unknown"


class AIErrorHandler:
    """
    Intelligent error classification and handling
    """
    
    # Error patterns for classification
    ERROR_PATTERNS = {
        ErrorType.QUOTA_EXCEEDED: [
            r'429',
            r'rate.?limit',
            r'quota.?exceeded',
            r'insufficient.?quota',
            r'billing.?hard.?limit',
            r'resource.?exhausted',
            r'too.?many.?requests'
        ],
        ErrorType.SERVICE_CRASH: [
            r'500',
            r'502',
            r'503',
            r'504',
            r'bad.?gateway',
            r'service.?unavailable',
            r'internal.?server.?error',
            r'connection.?reset'
        ],
        ErrorType.TIMEOUT: [
            r'timeout',
            r'timed.?out',
            r'deadline.?exceeded',
            r'read.?timeout',
            r'connection.?timeout'
        ],
        ErrorType.INVALID_REQUEST: [
            r'400',
            r'invalid.?request',
            r'bad.?request',
            r'malformed',
            r'invalid.?json'
        ],
        ErrorType.AUTHENTICATION: [
            r'401',
            r'403',
            r'unauthorized',
            r'forbidden',
            r'invalid.?api.?key',
            r'authentication.?failed'
        ],
        ErrorType.NETWORK: [
            r'network.?error',
            r'connection.?refused',
            r'connection.?error',
            r'dns.?resolution',
            r'failed.?to.?fetch'
        ]
    }
    
    # Retry strategies
    RETRY_STRATEGIES = {
        ErrorType.QUOTA_EXCEEDED: {
            'should_retry': False,  # Don't retry, switch provider
            'should_fallback': True,
            'retry_delay': 0
        },
        ErrorType.SERVICE_CRASH: {
            'should_retry': True,
            'should_fallback': True,
            'retry_delay': 5,
            'max_retries': 2
        },
        ErrorType.TIMEOUT: {
            'should_retry': True,
            'should_fallback': False,
            'retry_delay': 3,
            'max_retries': 3
        },
        ErrorType.INVALID_REQUEST: {
            'should_retry': False,  # Don't retry bad requests
            'should_fallback': False,
            'retry_delay': 0
        },
        ErrorType.AUTHENTICATION: {
            'should_retry': False,
            'should_fallback': True,  # Try other provider
            'retry_delay': 0
        },
        ErrorType.NETWORK: {
            'should_retry': True,
            'should_fallback': False,
            'retry_delay': 2,
            'max_retries': 3
        },
        ErrorType.UNKNOWN: {
            'should_retry': True,
            'should_fallback': True,
            'retry_delay': 2,
            'max_retries': 2
        }
    }
    
    def classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error into specific type
        
        Args:
            error: Exception object
        
        Returns:
            ErrorType enum
        """
        error_str = str(error).lower()
        
        # Check HTTP status codes
        if hasattr(error, 'status_code'):
            status_code = error.status_code
            if status_code == 429:
                return ErrorType.QUOTA_EXCEEDED
            elif status_code in [500, 502, 503, 504]:
                return ErrorType.SERVICE_CRASH
            elif status_code in [400]:
                return ErrorType.INVALID_REQUEST
            elif status_code in [401, 403]:
                return ErrorType.AUTHENTICATION
        
        # Pattern matching
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_str, re.IGNORECASE):
                    app_logger.debug(f"Error matched pattern '{pattern}' → {error_type}")
                    return error_type
        
        app_logger.warning(f"Error could not be classified: {error_str}")
        return ErrorType.UNKNOWN
    
    def should_retry(self, error_type: ErrorType) -> bool:
        """
        Determine if we should retry this error
        """
        strategy = self.RETRY_STRATEGIES.get(error_type, {})
        return strategy.get('should_retry', False)
    
    def should_fallback(self, error_type: ErrorType) -> bool:
        """
        Determine if we should fallback to another provider
        """
        strategy = self.RETRY_STRATEGIES.get(error_type, {})
        return strategy.get('should_fallback', False)
    
    def get_retry_delay(self, error_type: ErrorType) -> int:
        """
        Get retry delay in seconds
        """
        strategy = self.RETRY_STRATEGIES.get(error_type, {})
        return strategy.get('retry_delay', 2)
    
    def get_max_retries(self, error_type: ErrorType) -> int:
        """
        Get maximum retry attempts
        """
        strategy = self.RETRY_STRATEGIES.get(error_type, {})
        return strategy.get('max_retries', 3)
    
    def get_user_message(self, error_type: ErrorType) -> str:
        """
        Get user-friendly error message
        """
        messages = {
            ErrorType.QUOTA_EXCEEDED: "تم تجاوز الحد المسموح من الطلبات. نحاول مزود خدمة بديل...",
            ErrorType.SERVICE_CRASH: "الخدمة غير متوفرة مؤقتاً. نحاول مزود خدمة بديل...",
            ErrorType.TIMEOUT: "انتهت مهلة الاتصال. نعيد المحاولة...",
            ErrorType.INVALID_REQUEST: "خطأ في البيانات المرسلة. يرجى التحقق من المدخلات.",
            ErrorType.AUTHENTICATION: "مشكلة في المصادقة. نحاول مزود خدمة بديل...",
            ErrorType.NETWORK: "خطأ في الاتصال بالشبكة. نعيد المحاولة...",
            ErrorType.UNKNOWN: "حدث خطأ غير متوقع. نحاول حلول بديلة..."
        }
        return messages.get(error_type, "حدث خطأ. نحاول إيجاد حل...")
    
    def get_technical_details(self, error: Exception, error_type: ErrorType) -> Dict[str, Any]:
        """
        Get technical error details for logging
        """
        return {
            'error_type': error_type,
            'error_class': error.__class__.__name__,
            'error_message': str(error),
            'should_retry': self.should_retry(error_type),
            'should_fallback': self.should_fallback(error_type),
            'retry_delay': self.get_retry_delay(error_type),
            'max_retries': self.get_max_retries(error_type),
            'user_message': self.get_user_message(error_type)
        }
    
    def is_retriable_error(self, error: Exception) -> bool:
        """
        Quick check if error is retriable
        """
        error_type = self.classify_error(error)
        return self.should_retry(error_type)
    
    def is_quota_error(self, error: Exception) -> bool:
        """
        Quick check if error is quota-related
        """
        error_type = self.classify_error(error)
        return error_type == ErrorType.QUOTA_EXCEEDED
    
    def is_fatal_error(self, error: Exception) -> bool:
        """
        Check if error is fatal (should not retry or fallback)
        """
        error_type = self.classify_error(error)
        return error_type == ErrorType.INVALID_REQUEST


# Example usage in logs
def log_error_details(error: Exception):
    """
    Log comprehensive error details
    """
    handler = AIErrorHandler()
    error_type = handler.classify_error(error)
    details = handler.get_technical_details(error, error_type)
    
    app_logger.error(
        f"AI Provider Error Details:\n"
        f"  Type: {details['error_type']}\n"
        f"  Class: {details['error_class']}\n"
        f"  Message: {details['error_message']}\n"
        f"  Should Retry: {details['should_retry']}\n"
        f"  Should Fallback: {details['should_fallback']}\n"
        f"  User Message: {details['user_message']}"
    )