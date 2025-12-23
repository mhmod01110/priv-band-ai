# ============================================
# File: app/services/openai/service.py
# ============================================
"""
OpenAI Service - الواجهة الرئيسية
"""
from typing import Dict, Any
from app.logger import app_logger
from .light_model import LightModelClient
from .heavy_model import HeavyModelClient

class OpenAIService:
    """
    الخدمة الرئيسية - تربط بين كل الـ Models
    """
    def __init__(self):
        self.light_client = LightModelClient()
        self.heavy_client = HeavyModelClient()
        self.logger = app_logger
    
    # ============================================
    # Stage 1: Policy Match Check (Light Model)
    # ============================================
    
    async def check_policy_match(
        self,
        policy_type: str,
        policy_text: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        Stage 1: التحقق من مطابقة السياسة
        ✨ يستخدم Light Model
        """
        self.logger.info(f"📋 Stage 1: Policy match check - Type: {policy_type}")
        
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
        
        # استخدام Light Model 🪶
        result = await self.light_client.call(prompt, json_response=True)
        
        # تسجيل الاستجابة
        self.logger.log_response(
            stage="stage1_match",
            shop_name="NA",
            policy_type=policy_type,
            response=result
        )
        
        return result
    
    # ============================================
    # Stage 2: Compliance Analysis (Heavy Model)
    # ============================================
    
    async def analyze_compliance(
        self,
        shop_name: str,
        shop_specialization: str,
        policy_type: str,
        policy_text: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        Stage 2: تحليل الامتثال القانوني
        ✨ يستخدم Heavy Model
        """
        self.logger.info(f"🔍 Stage 2: Compliance analysis - Shop: {shop_name}")
        
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
        
        # استخدام Heavy Model 🔥
        result = await self.heavy_client.call(prompt, json_response=True)
        
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
    
    # ============================================
    # Stage 4: Policy Regeneration (Heavy Model)
    # ============================================
    
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
        Stage 4: إعادة كتابة السياسة
        ✨ يستخدم Heavy Model
        """
        self.logger.info(f"✍️ Stage 4: Policy regeneration - Shop: {shop_name}")
        
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
        
        # استخدام Heavy Model 🔥
        result = await self.heavy_client.call(prompt, json_response=True)
        
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
    
    # ============================================
    # Policy Comparison (Heavy Model)
    # ============================================
    
    async def compare_policies(
        self,
        original_policy: str,
        improved_policy: str,
        policy_type: str,
        prompt_generator
    ) -> Dict[str, Any]:
        """
        مقارنة النسخ المختلفة
        ✨ يستخدم Heavy Model
        """
        self.logger.info(f"⚖️ Comparing policies - Type: {policy_type}")
        
        prompt = prompt_generator(original_policy, improved_policy, policy_type)
        
        # استخدام Heavy Model 🔥
        result = await self.heavy_client.call(prompt, json_response=True)
        
        return result
