"""
API Safeguards - نظام حماية شامل للـ API
"""

import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, validator
import asyncio

# =============================================================================
# Rate Limiting - تحديد معدل الطلبات
# =============================================================================

class RateLimiter:
    """
    نظام تحديد معدل الطلبات لمنع الإساءة
    """
    
    def __init__(self):
        # تخزين عدد الطلبات لكل IP
        self.requests: Dict[str, list] = defaultdict(list)
        # تخزين IPs المحظورة مؤقتاً
        self.blocked_ips: Dict[str, datetime] = {}
        
    def is_rate_limited(
        self,
        identifier: str,
        max_requests: int = 10,
        window_seconds: int = 60,
        block_duration_minutes: int = 15
    ) -> tuple[bool, Optional[str]]:
        """
        فحص ما إذا كان المستخدم تجاوز الحد المسموح
        
        Args:
            identifier: IP أو معرف المستخدم
            max_requests: الحد الأقصى للطلبات
            window_seconds: النافذة الزمنية بالثواني
            block_duration_minutes: مدة الحظر بالدقائق
        
        Returns:
            (is_limited, reason)
        """
        now = datetime.now()
        
        # فحص إذا كان IP محظور
        if identifier in self.blocked_ips:
            unblock_time = self.blocked_ips[identifier]
            if now < unblock_time:
                remaining = (unblock_time - now).seconds // 60
                return True, f"IP محظور. سيتم إلغاء الحظر بعد {remaining} دقيقة"
            else:
                # انتهى وقت الحظر
                del self.blocked_ips[identifier]
        
        # تنظيف الطلبات القديمة
        cutoff_time = now - timedelta(seconds=window_seconds)
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff_time
        ]
        
        # فحص عدد الطلبات
        if len(self.requests[identifier]) >= max_requests:
            # حظر IP
            self.blocked_ips[identifier] = now + timedelta(minutes=block_duration_minutes)
            return True, f"تجاوزت الحد المسموح ({max_requests} طلبات/{window_seconds} ثانية). تم حظرك لمدة {block_duration_minutes} دقيقة"
        
        # إضافة الطلب الحالي
        self.requests[identifier].append(now)
        return False, None
    
    def get_remaining_requests(self, identifier: str, max_requests: int = 10) -> int:
        """الحصول على عدد الطلبات المتبقية"""
        return max(0, max_requests - len(self.requests.get(identifier, [])))

# =============================================================================
# Input Validation - التحقق من المدخلات
# =============================================================================

class InputSanitizer:
    """
    تنظيف والتحقق من المدخلات
    """
    
    # الحدود القصوى
    MAX_TEXT_LENGTH = 50000  # 50K characters
    MIN_TEXT_LENGTH = 50
    MAX_SHOP_NAME_LENGTH = 200
    MAX_SPECIALIZATION_LENGTH = 200
    
    # أنماط مشبوهة
    SUSPICIOUS_PATTERNS = [
        'javascript:',
        '<script',
        'onerror=',
        'onclick=',
        'eval(',
        'exec(',
        '__import__',
        'os.system',
        'subprocess',
    ]
    
    @staticmethod
    def validate_text_length(text: str, field_name: str) -> tuple[bool, Optional[str]]:
        """التحقق من طول النص"""
        length = len(text)
        
        if length < InputSanitizer.MIN_TEXT_LENGTH:
            return False, f"{field_name} قصير جداً. الحد الأدنى {InputSanitizer.MIN_TEXT_LENGTH} حرف"
        
        if length > InputSanitizer.MAX_TEXT_LENGTH:
            return False, f"{field_name} طويل جداً. الحد الأقصى {InputSanitizer.MAX_TEXT_LENGTH} حرف"
        
        return True, None
    
    @staticmethod
    def check_suspicious_content(text: str) -> tuple[bool, Optional[str]]:
        """فحص المحتوى المشبوه"""
        text_lower = text.lower()
        
        for pattern in InputSanitizer.SUSPICIOUS_PATTERNS:
            if pattern in text_lower:
                return False, f"محتوى مشبوه تم اكتشافه: {pattern}"
        
        return True, None
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """تنظيف النص من المحتوى الخطير"""
        # إزالة المسافات الزائدة
        text = ' '.join(text.split())
        
        # إزالة أحرف التحكم
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        return text.strip()
    
    @staticmethod
    def validate_policy_type(policy_type: str) -> bool:
        """التحقق من نوع السياسة"""
        valid_types = [
            "سياسات الاسترجاع و الاستبدال",
            "سياسة الحساب و الخصوصية",
            "سياسة الشحن و التوصيل"
        ]
        return policy_type in valid_types

# =============================================================================
# OpenAI API Safeguards - حماية استدعاءات OpenAI
# =============================================================================

class OpenAISafeguard:
    """
    حماية استدعاءات OpenAI API
    """
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.timeout = 120  # 2 minutes
        self.max_tokens_per_request = 16000
        self.max_prompt_tokens = 16000
        
        # تتبع الاستخدام
        self.daily_requests = defaultdict(int)
        self.daily_tokens = defaultdict(int)
        self.last_reset = datetime.now().date()
    
    def check_daily_limits(
        self,
        max_daily_requests: int = 1000,
        max_daily_tokens: int = 1000000
    ) -> tuple[bool, Optional[str]]:
        """
        فحص حدود الاستخدام اليومية
        """
        today = datetime.now().date()
        
        # إعادة تعيين العدادات اليومية
        if today > self.last_reset:
            self.daily_requests.clear()
            self.daily_tokens.clear()
            self.last_reset = today
        
        # فحص عدد الطلبات
        if self.daily_requests[today] >= max_daily_requests:
            return False, f"تم تجاوز الحد اليومي للطلبات ({max_daily_requests})"
        
        # فحص عدد الـ tokens
        if self.daily_tokens[today] >= max_daily_tokens:
            return False, f"تم تجاوز الحد اليومي للـ tokens ({max_daily_tokens})"
        
        return True, None
    
    def increment_usage(self, tokens_used: int):
        """زيادة عدادات الاستخدام"""
        today = datetime.now().date()
        self.daily_requests[today] += 1
        self.daily_tokens[today] += tokens_used
    
    def estimate_tokens(self, text: str) -> int:
        """
        تقدير عدد الـ tokens (تقريبي)
        1 token ≈ 4 characters for English
        1 token ≈ 2-3 characters for Arabic
        """
        # نستخدم متوسط 2.5 حرف لكل token للنص العربي
        return len(text) // 2
    
    async def safe_api_call(self, api_func, *args, **kwargs):
        """
        استدعاء آمن لـ OpenAI API مع retry و timeout
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                # استخدام timeout
                result = await asyncio.wait_for(
                    api_func(*args, **kwargs),
                    timeout=self.timeout
                )
                return result
                
            except asyncio.TimeoutError:
                last_exception = Exception(f"انتهت مهلة الاستدعاء ({self.timeout} ثانية)")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
            except Exception as e:
                last_exception = e
                # إعادة المحاولة فقط للأخطاء المؤقتة
                if "rate_limit" in str(e).lower() or "timeout" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    # خطأ دائم، لا نعيد المحاولة
                    raise
        
        # فشلت جميع المحاولات
        raise Exception(f"فشل الاستدعاء بعد {self.max_retries} محاولات: {str(last_exception)}")

# =============================================================================
# Request Deduplication - منع الطلبات المكررة
# =============================================================================

class RequestDeduplicator:
    """
    منع معالجة نفس الطلب مرتين
    """
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes
        self.processed_requests: Dict[str, datetime] = {}
        self.ttl_seconds = ttl_seconds
    
    def generate_hash(self, request_data: Dict[str, Any]) -> str:
        """إنشاء hash فريد للطلب"""
        # ترتيب البيانات لضمان نفس الـ hash
        sorted_data = str(sorted(request_data.items()))
        return hashlib.sha256(sorted_data.encode()).hexdigest()
    
    def is_duplicate(self, request_hash: str) -> bool:
        """فحص إذا كان الطلب مكرر"""
        now = datetime.now()
        
        # تنظيف الطلبات القديمة
        expired_hashes = [
            h for h, timestamp in self.processed_requests.items()
            if (now - timestamp).seconds > self.ttl_seconds
        ]
        for h in expired_hashes:
            del self.processed_requests[h]
        
        # فحص إذا كان موجود
        if request_hash in self.processed_requests:
            return True
        
        # تسجيل الطلب الجديد
        self.processed_requests[request_hash] = now
        return False

# =============================================================================
# Circuit Breaker - قاطع الدائرة
# =============================================================================

class CircuitBreaker:
    """
    قاطع دائرة لمنع استدعاء خدمة معطلة
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def call(self, func):
        """تزيين دالة بـ circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "open":
                # فحص إذا حان وقت المحاولة
                if (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout:
                    self.state = "half_open"
                else:
                    raise Exception("الخدمة معطلة مؤقتاً. الرجاء المحاولة لاحقاً")
            
            try:
                result = await func(*args, **kwargs)
                # نجحت المحاولة
                if self.state == "half_open":
                    self.state = "closed"
                    self.failure_count = 0
                return result
                
            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = datetime.now()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                
                raise
        
        return wrapper

# =============================================================================
# Content Filter - تصفية المحتوى
# =============================================================================

class ContentFilter:
    """
    تصفية المحتوى غير المناسب
    """
    
    # كلمات محظورة (يمكن توسيعها)
    BLOCKED_WORDS = [
        'spam', 'hack', 'crack', 'exploit',
        # أضف كلمات أخرى حسب الحاجة
    ]
    
    @staticmethod
    def contains_blocked_content(text: str) -> tuple[bool, Optional[str]]:
        """فحص المحتوى المحظور"""
        text_lower = text.lower()
        
        for word in ContentFilter.BLOCKED_WORDS:
            if word in text_lower:
                return True, f"تم اكتشاف محتوى محظور"
        
        return False, None
    
    @staticmethod
    def check_repetitive_content(text: str, max_repetition: int = 10) -> tuple[bool, Optional[str]]:
        """فحص التكرار المفرط"""
        words = text.split()
        if not words:
            return True, None
        
        # فحص تكرار نفس الكلمة
        from collections import Counter
        word_counts = Counter(words)
        most_common_word, count = word_counts.most_common(1)[0]
        
        if count > max_repetition and len(most_common_word) > 3:
            repetition_ratio = count / len(words)
            if repetition_ratio > 0.3:  # أكثر من 30% تكرار
                return False, f"تكرار مفرط تم اكتشافه"
        
        return True, None

# =============================================================================
# Global Instances - نسخ عامة
# =============================================================================

rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()
openai_safeguard = OpenAISafeguard()
request_deduplicator = RequestDeduplicator()
content_filter = ContentFilter()

# Circuit breaker للـ OpenAI API
openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=120,
    expected_exception=Exception
)