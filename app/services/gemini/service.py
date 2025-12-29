"""
Gemini Service - خدمة Google Gemini AI
توفر واجهة موحدة مع OpenAI Service
يدعم موديلات متعددة (Light & Heavy)
"""

import json
import time
import traceback
import google.generativeai as genai
from typing import Dict, Any, Literal
from app.config import get_settings
from app.logger import app_logger
from app.safeguards import openai_safeguard, openai_circuit_breaker
from app.prompts.system_prompt import SYSTEM_PROMPT

settings = get_settings()

class GeminiService:
    def __init__(self):
        """تهيئة خدمة Gemini"""
        # تكوين Gemini
        genai.configure(api_key=settings.gemini_api_key)
        
        # Light Model Configuration (للمهام السهلة - Stage 1)
        self.light_model_name = settings.gemini_light_model
        self.light_temperature = settings.gemini_light_temperature
        self.light_max_tokens = settings.gemini_light_max_tokens
        
        # Heavy Model Configuration (للمهام الصعبة - Stage 2-4)
        self.heavy_model_name = settings.gemini_heavy_model
        self.heavy_temperature = settings.gemini_heavy_temperature
        self.heavy_max_tokens = settings.gemini_heavy_max_tokens
        
        self.logger = app_logger
        self.safeguard = openai_safeguard
        
        # إنشاء النماذج
        self.light_model = genai.GenerativeModel(
            model_name=self.light_model_name,
            generation_config={
                "temperature": self.light_temperature,
                "max_output_tokens": self.light_max_tokens,
            }
        )
        
        self.heavy_model = genai.GenerativeModel(
            model_name=self.heavy_model_name,
            generation_config={
                "temperature": self.heavy_temperature,
                "max_output_tokens": self.heavy_max_tokens,
            }
        )
    
    async def analyze_with_prompt(
        self,
        prompt: str,
        json_response: bool = True,
        model_type: Literal["light", "heavy"] = "heavy"
    ) -> Dict[str, Any]:
        """
        إرسال Prompt إلى Gemini والحصول على النتيجة - مع حماية كاملة
        
        Args:
            prompt: النص المطلوب
            json_response: هل الاستجابة JSON؟
            model_type: "light" للموديل الخفيف أو "heavy" للموديل القوي
        """
        start_time = time.time()
        
        # اختيار الموديل المناسب
        if model_type == "light":
            model = self.light_model
            model_name = self.light_model_name
            temperature = self.light_temperature
            max_tokens = self.light_max_tokens
            self.logger.debug(f"🪶 Using LIGHT model: {model_name}")
        else:
            model = self.heavy_model
            model_name = self.heavy_model_name
            temperature = self.heavy_temperature
            max_tokens = self.heavy_max_tokens
            self.logger.debug(f"🔥 Using HEAVY model: {model_name}")
        
        # 1. فحص حدود الاستخدام اليومية
        can_proceed, limit_reason = self.safeguard.check_daily_limits(
            max_daily_requests=1000,
            max_daily_tokens=1000000
        )
        
        if not can_proceed:
            self.logger.error(f"Daily limit exceeded: {limit_reason}")
            raise Exception(f"تم تجاوز الحد اليومي: {limit_reason}")
        
        # 2. تقدير عدد الـ tokens
        estimated_tokens = self.safeguard.estimate_tokens(prompt)
        
        if estimated_tokens > self.safeguard.max_prompt_tokens:
            self.logger.error(f"Prompt too long: {estimated_tokens} tokens")
            raise Exception(
                f"النص طويل جداً ({estimated_tokens} tokens). "
                f"الحد الأقصى {self.safeguard.max_prompt_tokens} tokens"
            )
        
        self.logger.debug(f"Estimated tokens: {estimated_tokens}")
        
        try:
            self.logger.debug(f"Sending request to Gemini - Model: {model_name}")
            
            # 3. استدعاء آمن مع retry و timeout و circuit breaker
            @openai_circuit_breaker.call
            async def make_api_call():
                # إضافة System Prompt للـ prompt
                full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
                
                # استدعاء Gemini (sync API لكن نلفها في async)
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: model.generate_content(full_prompt)
                )
                return response
            
            # استخدام safe_api_call للحصول على retry و timeout
            response = await self.safeguard.safe_api_call(make_api_call)
            
            duration = time.time() - start_time
            content = response.text
            
            # 4. تسجيل الاستخدام (تقديري لأن Gemini لا يعطي token count مباشرة)
            total_tokens = estimated_tokens + len(content) // 2
            self.safeguard.increment_usage(total_tokens)
            
            self.logger.info(
                f"Gemini API call successful ({model_type.upper()} model) - "
                f"Model: {model_name} - "
                f"Duration: {duration:.2f}s - "
                f"Estimated tokens: {total_tokens}"
            )
            
            # 5. معالجة الاستجابة
            if json_response:
                # محاولة تنظيف JSON إذا كان يحتوي على نص إضافي
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                try:
                    parsed_response = json.loads(content)
                    return parsed_response
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON decode error: {e}")
                    self.logger.debug(f"Received content (first 500 chars): {content[:500]}")
                    raise ValueError(f"فشل في تحويل الاستجابة إلى JSON: {str(e)}")
            
            return {"content": content}
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            tb = traceback.format_exc()
            
            self.logger.log_error(
                error_type=type(e).__name__,
                error_message=error_msg,
                traceback_info=tb
            )
            
            self.logger.error(
                f"Gemini API call failed - "
                f"Duration: {duration:.2f}s - "
                f"Error: {error_msg}"
            )
            raise
    
    async def check_policy_match(
        self,
        policy_type: str,
        policy_text: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        التحقق من مطابقة نص السياسة مع النوع المحدد
        ✨ يستخدم LIGHT MODEL لأنها مهمة بسيطة
        """
        self.logger.info(f"Stage 1: Checking policy match - Type: {policy_type}")
        
        prompt = prompt_generator(policy_type, policy_text)
        
        # تسجيل الـ Prompt
        self.logger.log_prompt(
            stage="stage1_match",
            shop_name="NA",
            policy_type=policy_type,
            prompt=prompt,
            metadata={
                "policy_text_length": len(policy_text),
                "provider": "gemini",
                "model_type": "light"
            }
        )
        
        # استخدام LIGHT MODEL 🪶
        result = await self.analyze_with_prompt(
            prompt,
            json_response=True,
            model_type="light"
        )
        
        # تسجيل الاستجابة
        self.logger.log_response(
            stage="stage1_match",
            shop_name="NA",
            policy_type=policy_type,
            response=result,
            metadata={"provider": "gemini", "model_type": "light"}
        )
        
        return result
    
    async def analyze_compliance(
        self,
        shop_name: str,
        shop_specialization: str,
        policy_type: str,
        policy_text: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        تحليل الامتثال القانوني الشامل
        ✨ يستخدم HEAVY MODEL لأنها مهمة معقدة
        """
        self.logger.info(
            f"Stage 2: Analyzing compliance - Shop: {shop_name} - Type: {policy_type}"
        )
        
        prompt = prompt_generator(shop_name, shop_specialization, policy_type, policy_text)
        
        # تسجيل الـ Prompt
        self.logger.log_prompt(
            stage="stage2_analyze",
            shop_name=shop_name,
            policy_type=policy_type,
            prompt=prompt,
            metadata={
                "shop_specialization": shop_specialization,
                "policy_text_length": len(policy_text),
                "provider": "gemini",
                "model_type": "heavy"
            }
        )
        
        # استخدام HEAVY MODEL 🔥
        result = await self.analyze_with_prompt(
            prompt,
            json_response=True,
            model_type="heavy"
        )
        
        # تسجيل الاستجابة
        self.logger.log_response(
            stage="stage2_analyze",
            shop_name=shop_name,
            policy_type=policy_type,
            response=result,
            metadata={
                "overall_compliance": result.get("overall_compliance_ratio", 0),
                "critical_issues_count": len(result.get("critical_issues", [])),
                "provider": "gemini",
                "model_type": "heavy"
            }
        )
        
        return result
    
    async def regenerate_policy(
        self,
        shop_name: str,
        shop_specialization: str,
        policy_type: str,
        original_policy: str,
        compliance_report: dict,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        Stage 4: إعادة كتابة السياسة بنسخة محسّنة
        ✨ يستخدم HEAVY MODEL لأنها مهمة معقدة جداً
        """
        self.logger.info(
            f"Stage 4: Regenerating improved policy - Shop: {shop_name} - Type: {policy_type}"
        )
        
        prompt = prompt_generator(
            shop_name,
            shop_specialization,
            policy_type,
            original_policy,
            compliance_report
        )
        
        # تسجيل الـ Prompt
        self.logger.log_prompt(
            stage="stage4_regenerate",
            shop_name=shop_name,
            policy_type=policy_type,
            prompt=prompt,
            metadata={
                "shop_specialization": shop_specialization,
                "original_policy_length": len(original_policy),
                "current_compliance": compliance_report.get('overall_compliance_ratio', 0),
                "provider": "gemini",
                "model_type": "heavy"
            }
        )
        
        # استخدام HEAVY MODEL 🔥
        result = await self.analyze_with_prompt(
            prompt,
            json_response=True,
            model_type="heavy"
        )
        
        # تسجيل الاستجابة
        self.logger.log_response(
            stage="stage4_regenerate",
            shop_name=shop_name,
            policy_type=policy_type,
            response=result,
            metadata={
                "improved_policy_length": len(result.get('improved_policy', '')),
                "estimated_new_compliance": result.get('estimated_new_compliance', 0),
                "improvements_count": len(result.get('improvements_made', [])),
                "provider": "gemini",
                "model_type": "heavy"
            }
        )
        
        return result
    
    async def compare_policies(
        self,
        original_policy: str,
        improved_policy: str,
        policy_type: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        مقارنة النسخة الأصلية بالمحسّنة
        ✨ يستخدم HEAVY MODEL
        """
        self.logger.info(f"Comparing original vs improved policy - Type: {policy_type}")
        
        prompt = prompt_generator(original_policy, improved_policy, policy_type)
        
        result = await self.analyze_with_prompt(
            prompt,
            json_response=True,
            model_type="heavy"
        )
        
        return result