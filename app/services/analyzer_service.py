from datetime import datetime
import time
import traceback
from typing import Dict, Any, Optional
from app.models import (
    PolicyAnalysisRequest,
    AnalysisResponse,
    PolicyMatchResult,
    ComplianceReport,
    CriticalIssue,
    CompliancePoint,
    WeaknessPoint,
    AmbiguityPoint,
    ImprovedPolicyResult,
    ImprovementDetail
)
from app.services.openai import OpenAIService
from app.services.gemini_service import GeminiService
from app.prompts.policy_matcher import get_policy_matcher_prompt
from app.prompts.compliance_analyzer import get_compliance_analyzer_prompt
from app.prompts.policy_generator import get_policy_regeneration_prompt
from app.logger import app_logger
from app.config import get_settings

settings = get_settings()

class AnalyzerService:
    def __init__(self, provider: Optional[str] = None):
        """
        تهيئة خدمة التحليل
        
        Args:
            provider: المزود المستخدم ("openai" أو "gemini")
                     إذا لم يحدد، سيستخدم الإعداد الافتراضي
        """
        self.provider = provider or settings.ai_provider
        self.logger = app_logger
        
        # اختيار الخدمة المناسبة
        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API Key غير موجود في الإعدادات")
            self.ai_service = OpenAIService()
            self.logger.info("✅ Using OpenAI as AI provider")
        elif self.provider == "gemini":
            if not settings.gemini_api_key:
                raise ValueError("Gemini API Key غير موجود في الإعدادات")
            self.ai_service = GeminiService()
            self.logger.info("✅ Using Gemini as AI provider")
        else:
            raise ValueError(f"مزود غير مدعوم: {self.provider}. استخدم 'openai' أو 'gemini'")
    
    async def analyze_policy(self, request: PolicyAnalysisRequest) -> AnalysisResponse:
        """
        المعالج الرئيسي لتحليل السياسة
        """
        timestamp = datetime.now().isoformat()
        start_time = time.time()
        
        self.logger.info("="*80)
        self.logger.info(f"🚀 Starting new analysis with {self.provider.upper()}")
        self.logger.info(f"Shop: {request.shop_name}")
        self.logger.info(f"Specialization: {request.shop_specialization}")
        self.logger.info(f"Policy Type: {request.policy_type.value}")
        self.logger.info(f"Policy Text Length: {len(request.policy_text)} characters")
        self.logger.info("="*80)
        
        try:
            # Stage 1: التحقق من مطابقة نوع السياسة
            self.logger.info("▶ Stage 1: Policy Match Check")
            match_result = await self._check_policy_match(
                request.policy_type.value,
                request.policy_text
            )
            
            # إذا لم تكن مطابقة، نرجع رسالة خطأ
            if not match_result.is_matched:
                duration = time.time() - start_time
                self.logger.warning(
                    f"❌ Policy mismatch detected - Confidence: {match_result.confidence}%"
                )
                self.logger.log_analysis_summary(
                    shop_name=request.shop_name,
                    policy_type=request.policy_type.value,
                    compliance_ratio=0,
                    duration=duration,
                    success=False
                )
                
                return AnalysisResponse(
                    success=False,
                    message=f"نوع السياسة المحدد لا يطابق محتوى النص. {match_result.reason}",
                    policy_match=match_result,
                    compliance_report=None,
                    shop_name=request.shop_name,
                    shop_specialization=request.shop_specialization,
                    policy_type=request.policy_type,
                    analysis_timestamp=timestamp
                )
            
            self.logger.info(
                f"✅ Policy matched - Confidence: {match_result.confidence}%"
            )
            
            # Stage 2 & 3: تحليل الامتثال القانوني وإنشاء التقرير
            self.logger.info("▶ Stage 2: Compliance Analysis")
            compliance_report = await self._analyze_compliance(
                request.shop_name,
                request.shop_specialization,
                request.policy_type.value,
                request.policy_text
            )
            
            # Stage 4: إعادة كتابة السياسة بنسخة محسّنة
            improved_policy_result = None
            if compliance_report.overall_compliance_ratio < 95:
                self.logger.info("▶ Stage 4: Regenerating Improved Policy")
                improved_policy_result = await self._regenerate_policy(
                    request.shop_name,
                    request.shop_specialization,
                    request.policy_type.value,
                    request.policy_text,
                    compliance_report
                )
                self.logger.info(
                    f"✅ Improved policy generated - "
                    f"New compliance: {improved_policy_result.estimated_new_compliance}%"
                )
            else:
                self.logger.info("ℹ️  Policy already has excellent compliance (≥95%), skipping regeneration")
            
            duration = time.time() - start_time
            
            self.logger.info(
                f"✅ Analysis completed successfully - "
                f"Compliance: {compliance_report.overall_compliance_ratio}% - "
                f"Duration: {duration:.2f}s"
            )
            
            # تسجيل ملخص التحليل
            self.logger.log_analysis_summary(
                shop_name=request.shop_name,
                policy_type=request.policy_type.value,
                compliance_ratio=compliance_report.overall_compliance_ratio,
                duration=duration,
                success=True
            )
            
            return AnalysisResponse(
                success=True,
                message="تم التحليل بنجاح",
                policy_match=match_result,
                compliance_report=compliance_report,
                improved_policy=improved_policy_result,
                shop_name=request.shop_name,
                shop_specialization=request.shop_specialization,
                policy_type=request.policy_type,
                analysis_timestamp=timestamp
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            tb = traceback.format_exc()
            
            self.logger.log_error(
                error_type=type(e).__name__,
                error_message=error_msg,
                shop_name=request.shop_name,
                traceback_info=tb
            )
            
            self.logger.error(
                f"❌ Analysis failed - "
                f"Duration: {duration:.2f}s - "
                f"Error: {error_msg}"
            )
            
            return AnalysisResponse(
                success=False,
                message=f"حدث خطأ أثناء التحليل: {error_msg}",
                policy_match=None,
                compliance_report=None,
                shop_name=request.shop_name,
                shop_specialization=request.shop_specialization,
                policy_type=request.policy_type,
                analysis_timestamp=timestamp
            )
    
    async def _check_policy_match(
        self,
        policy_type: str,
        policy_text: str
    ) -> PolicyMatchResult:
        """
        Stage 1: التحقق من مطابقة نوع السياسة
        """
        result = await self.ai_service.check_policy_match(
            policy_type,
            policy_text,
            get_policy_matcher_prompt
        )
        
        return PolicyMatchResult(
            is_matched=result.get("is_matched", False),
            confidence=result.get("confidence", 0),
            reason=result.get("reason", "")
        )
    
    async def _analyze_compliance(
        self,
        shop_name: str,
        shop_specialization: str,
        policy_type: str,
        policy_text: str
    ) -> ComplianceReport:
        """
        Stage 2: تحليل الامتثال القانوني
        """
        result = await self.ai_service.analyze_compliance(
            shop_name,
            shop_specialization,
            policy_type,
            policy_text,
            get_compliance_analyzer_prompt
        )
        
        # تحويل النتيجة إلى نموذج Pydantic
        critical_issues = [
            CriticalIssue(**issue)
            for issue in result.get("critical_issues", [])
        ]
        
        strengths = [
            CompliancePoint(**point)
            for point in result.get("strengths", [])
        ]
        
        weaknesses = [
            WeaknessPoint(**point)
            for point in result.get("weaknesses", [])
        ]
        
        ambiguities = [
            AmbiguityPoint(**point)
            for point in result.get("ambiguities", [])
        ]
        
        return ComplianceReport(
            overall_compliance_ratio=result.get("overall_compliance_ratio", 0),
            compliance_grade=result.get("compliance_grade", "غير محدد"),
            critical_issues=critical_issues,
            strengths=strengths,
            weaknesses=weaknesses,
            ambiguities=ambiguities,
            summary=result.get("summary", ""),
            recommendations=result.get("recommendations", [])
        )
    
    async def _regenerate_policy(
        self,
        shop_name: str,
        shop_specialization: str,
        policy_type: str,
        original_policy: str,
        compliance_report: ComplianceReport
    ) -> ImprovedPolicyResult:
        """
        Stage 4: إعادة كتابة السياسة بنسخة محسّنة
        """
        # تحويل compliance_report إلى dict
        report_dict = {
            "overall_compliance_ratio": compliance_report.overall_compliance_ratio,
            "compliance_grade": compliance_report.compliance_grade,
            "critical_issues": [
                {
                    "phrase": issue.phrase,
                    "severity": issue.severity,
                    "compliance_ratio": issue.compliance_ratio,
                    "suggestion": issue.suggestion,
                    "legal_reference": issue.legal_reference
                }
                for issue in compliance_report.critical_issues
            ],
            "weaknesses": [
                {
                    "issue": w.issue,
                    "exact_text": w.exact_text,
                    "compliance_ratio": w.compliance_ratio,
                    "suggestion": w.suggestion,
                    "legal_reference": w.legal_reference
                }
                for w in compliance_report.weaknesses
            ],
            "ambiguities": [
                {
                    "missing_standard": a.missing_standard,
                    "description": a.description,
                    "importance": a.importance,
                    "suggested_text": a.suggested_text
                }
                for a in compliance_report.ambiguities
            ],
            "strengths": [
                {
                    "requirement": s.requirement,
                    "status": s.status,
                    "found_text": s.found_text,
                    "compliance_ratio": s.compliance_ratio
                }
                for s in compliance_report.strengths
            ]
        }
        
        result = await self.ai_service.regenerate_policy(
            shop_name,
            shop_specialization,
            policy_type,
            original_policy,
            report_dict,
            get_policy_regeneration_prompt
        )
        
        # تحويل النتيجة إلى نموذج Pydantic
        improvements = [
            ImprovementDetail(**improvement)
            for improvement in result.get("improvements_made", [])
        ]
        
        return ImprovedPolicyResult(
            improved_policy=result.get("improved_policy", ""),
            improvements_made=improvements,
            compliance_enhancements=result.get("compliance_enhancements", []),
            structure_improvements=result.get("structure_improvements", []),
            estimated_new_compliance=result.get("estimated_new_compliance", 95),
            key_additions=result.get("key_additions", []),
            notes=result.get("notes")
        )