# ============================================
# File: app/services/openai/light_model.py
# ============================================
"""
Light Model Client - للمهام البسيطة (Stage 1)
"""
from typing import Dict, Any
from app.config import get_settings
from app.safeguards import openai_circuit_breaker
from app.prompts.system_prompt import SYSTEM_PROMPT
from .base_client import BaseOpenAIClient

settings = get_settings()

class LightModelClient(BaseOpenAIClient):
    """
    🪶 Light Model - للمهام السريعة والبسيطة
    يستخدم في Stage 1: Policy Match Check
    """
    def __init__(self):
        super().__init__()
        self.model = settings.openai_light_model
        self.temperature = settings.openai_light_temperature
        self.max_tokens = settings.openai_light_max_tokens
    
    async def call(self, prompt: str, json_response: bool = True) -> Dict[str, Any]:
        """
        استدعاء Light Model
        
        Args:
            prompt: النص المطلوب
            json_response: هل الاستجابة JSON؟
        """
        import time
        start_time = time.time()
        
        self.logger.debug(f"🪶 Calling LIGHT model: {self.model}")
        
        # 1. فحص الحدود
        self.check_usage_limits()
        
        # 2. تقدير الـ tokens
        self.estimate_and_validate_tokens(prompt)
        
        try:
            # 3. استدعاء API
            @openai_circuit_breaker.call
            async def make_api_call():
                return await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=min(self.max_tokens, self.safeguard.max_tokens_per_request),
                    response_format={"type": "json_object"} if json_response else {"type": "text"}
                )
            
            response = await self.safeguard.safe_api_call(make_api_call)
            
            # 4. معالجة النتيجة
            duration = time.time() - start_time
            content = response.choices[0].message.content
            usage = response.usage
            
            self.safeguard.increment_usage(usage.total_tokens)
            
            self.logger.info(
                f"✅ LIGHT model success - Duration: {duration:.2f}s - "
                f"Tokens: {usage.total_tokens}"
            )
            
            # 5. إرجاع النتيجة
            if json_response:
                return self.parse_json_response(content)
            return {"content": content}
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_api_error(e, duration, "LIGHT")
            raise

