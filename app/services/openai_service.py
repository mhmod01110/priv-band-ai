import json
import time
import traceback
from openai import AsyncOpenAI
from typing import Dict, Any, Literal
from app.config import get_settings
from app.logger import app_logger
from app.safeguards import openai_safeguard, openai_circuit_breaker
from app.prompts.system_prompt import SYSTEM_PROMPT

settings = get_settings()

class OpenAIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Light Model Configuration (للمهام السهلة - Stage 1)
        self.light_model = settings.openai_light_model
        self.light_temperature = settings.openai_light_temperature
        self.light_max_tokens = settings.openai_light_max_tokens
        
        # Heavy Model Configuration (للمهام الصعبة - Stage 2-4)
        self.heavy_model = settings.openai_heavy_model
        self.heavy_temperature = settings.openai_heavy_temperature
        self.heavy_max_tokens = settings.openai_heavy_max_tokens
        
        self.logger = app_logger
        self.safeguard = openai_safeguard
    
    async def analyze_with_prompt(
        self,
        prompt: str,
        json_response: bool = True,
        model_type: Literal["light", "heavy"] = "heavy"
    ) -> Dict[str, Any]:
        """
        إرسال Prompt إلى OpenAI والحصول على النتيجة - مع حماية كاملة
        
        Args:
            prompt: النص المطلوب
            json_response: هل الاستجابة JSON؟
            model_type: "light" للموديل الخفيف (Stage 1) أو "heavy" للموديل القوي (Stage 2-4)
        """
        start_time = time.time()
        
        # اختيار الموديل المناسب
        if model_type == "light":
            model = self.light_model
            temperature = self.light_temperature
            max_tokens = self.light_max_tokens
            self.logger.debug(f"🪶 Using LIGHT model: {model} (Stage 1 - Simple task)")
        else:
            model = self.heavy_model
            temperature = self.heavy_temperature
            max_tokens = self.heavy_max_tokens
            self.logger.debug(f"🔥 Using HEAVY model: {model} (Stage 2-4 - Complex task)")
        
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
            self.logger.debug(f"Sending request to OpenAI - Model: {model}")
            
            # 3. استدعاء آمن مع retry و timeout و circuit breaker
            @openai_circuit_breaker.call
            async def make_api_call():
                # بناء الـ parameters الأساسية
                api_params = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": temperature,
                    "max_completion_tokens": min(max_tokens, self.safeguard.max_tokens_per_request),
                    "response_format": {"type": "json_object"} if json_response else {"type": "text"}
                }
                
                # 🔥 ملحوظة: reasoning parameter متاح فقط في responses.create() API الجديد
                # لما OpenAI يدعمه في chat.completions.create() هنضيفه هنا:
                # if model_type == "heavy":
                #     api_params["reasoning"] = {"effort": "high"}
                
                return await self.client.chat.completions.create(**api_params)
            
            # استخدام safe_api_call للحصول على retry و timeout
            response = await self.safeguard.safe_api_call(make_api_call)
            
            duration = time.time() - start_time
            content = response.choices[0].message.content
            
            # 4. تسجيل الاستخدام
            usage = response.usage
            self.safeguard.increment_usage(usage.total_tokens)
            
            self.logger.info(
                f"OpenAI API call successful ({model_type.upper()} model) - "
                f"Model: {model} - "
                f"Duration: {duration:.2f}s - "
                f"Tokens: {usage.total_tokens} "
                f"(Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens})"
            )
            
            # 5. معالجة الاستجابة
            if json_response:
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
                f"OpenAI API call failed - "
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
        Stage 1: التحقق من مطابقة نص السياسة مع النوع المحدد
        ✨ يستخدم LIGHT MODEL لأنها مهمة بسيطة - تحتاج سرعة فقط
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
            response=result
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
        Stage 2: تحليل الامتثال القانوني الشامل
        ✨ يستخدم HEAVY MODEL لأنها مهمة معقدة تحتاج تحليل عميق
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
                "critical_issues_count": len(result.get("critical_issues", []))
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
        Stage 4: إعادة كتابة السياسة بنسخة محسّنة ومطابقة للقانون
        ✨ يستخدم HEAVY MODEL لأنها مهمة معقدة جداً - تحتاج تفكير عميق
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
                "improvements_count": len(result.get('improvements_made', []))
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
        مقارنة النسخة الأصلية بالمحسّنة وتحديد الفروقات
        ✨ يستخدم HEAVY MODEL لتحليل الفروقات بدقة
        """
        self.logger.info(f"Comparing original vs improved policy - Type: {policy_type}")
        
        prompt = prompt_generator(original_policy, improved_policy, policy_type)
        
        # استخدام HEAVY MODEL 🔥
        result = await self.analyze_with_prompt(
            prompt,
            json_response=True,
            model_type="heavy"
        )
        
        return result