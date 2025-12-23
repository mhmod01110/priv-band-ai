# ============================================
# File: app/services/openai/base_client.py
# ============================================
"""
Base OpenAI Client - الأساسيات المشتركة
"""
import json
import time
import traceback
from openai import AsyncOpenAI
from typing import Dict, Any
from app.config import get_settings
from app.logger import app_logger
from app.safeguards import openai_safeguard

settings = get_settings()

class BaseOpenAIClient:
    """
    الـ Client الأساسي - يحتوي على العمليات المشتركة فقط
    """
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.logger = app_logger
        self.safeguard = openai_safeguard
    
    def check_usage_limits(self):
        """فحص حدود الاستخدام اليومية"""
        can_proceed, limit_reason = self.safeguard.check_daily_limits(
            max_daily_requests=1000,
            max_daily_tokens=1000000
        )
        
        if not can_proceed:
            self.logger.error(f"Daily limit exceeded: {limit_reason}")
            raise Exception(f"تم تجاوز الحد اليومي: {limit_reason}")
        
        return True
    
    def estimate_and_validate_tokens(self, prompt: str):
        """تقدير والتحقق من عدد الـ tokens"""
        estimated_tokens = self.safeguard.estimate_tokens(prompt)
        
        if estimated_tokens > self.safeguard.max_prompt_tokens:
            self.logger.error(f"Prompt too long: {estimated_tokens} tokens")
            raise Exception(
                f"النص طويل جداً ({estimated_tokens} tokens). "
                f"الحد الأقصى {self.safeguard.max_prompt_tokens} tokens"
            )
        
        self.logger.debug(f"Estimated tokens: {estimated_tokens}")
        return estimated_tokens
    
    def parse_json_response(self, content: str) -> Dict[str, Any]:
        """معالجة استجابة JSON من OpenAI"""
        content = content.strip()
        
        # إزالة markdown formatting
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            self.logger.debug(f"Received content (first 500 chars): {content[:500]}")
            raise ValueError(f"فشل في تحويل الاستجابة إلى JSON: {str(e)}")
    
    def log_api_error(self, error: Exception, duration: float, model_type: str):
        """تسجيل أخطاء API"""
        error_msg = str(error)
        tb = traceback.format_exc()
        
        self.logger.log_error(
            error_type=type(error).__name__,
            error_message=error_msg,
            traceback_info=tb
        )
        
        self.logger.error(
            f"❌ {model_type} model call failed - "
            f"Duration: {duration:.2f}s - "
            f"Error: {error_msg}"
        )
