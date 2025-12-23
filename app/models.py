from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum

class PolicyType(str, Enum):
    RETURN_EXCHANGE = "سياسات الاسترجاع و الاستبدال"
    PRIVACY_ACCOUNT = "سياسة الحساب و الخصوصية"
    SHIPPING_DELIVERY = "سياسة الشحن و التوصيل"

class PolicyAnalysisRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=200, description="اسم المتجر")
    shop_specialization: str = Field(..., min_length=2, max_length=200, description="تخصص المتجر")
    policy_type: PolicyType = Field(..., description="نوع السياسة")
    policy_text: str = Field(..., min_length=50, max_length=50000, description="نص السياسة")

    @field_validator('shop_name')
    @classmethod
    def validate_shop_name(cls, v: str) -> str:
        """التحقق من اسم المتجر"""
        # إزالة المسافات الزائدة
        v = ' '.join(v.split())
        
        # فحص الأحرف الخاصة المشبوهة
        suspicious_chars = ['<', '>', '{', '}', '[', ']', '\\', '|']
        if any(char in v for char in suspicious_chars):
            raise ValueError("اسم المتجر يحتوي على أحرف غير مسموحة")
        
        return v
    
    @field_validator('shop_specialization')
    @classmethod
    def validate_specialization(cls, v: str) -> str:
        """التحقق من تخصص المتجر"""
        v = ' '.join(v.split())
        
        suspicious_chars = ['<', '>', '{', '}', '[', ']', '\\', '|']
        if any(char in v for char in suspicious_chars):
            raise ValueError("تخصص المتجر يحتوي على أحرف غير مسموحة")
        
        return v
    
    @field_validator('policy_text')
    @classmethod
    def validate_policy_text(cls, v: str) -> str:
        """التحقق من نص السياسة"""
        from app.safeguards import input_sanitizer, content_filter
        
        # تنظيف النص
        v = input_sanitizer.sanitize_text(v)
        
        # فحص المحتوى المشبوه
        is_safe, reason = input_sanitizer.check_suspicious_content(v)
        if not is_safe:
            raise ValueError(f"نص السياسة يحتوي على محتوى مشبوه: {reason}")
        
        # فحص المحتوى المحظور
        is_blocked, reason = content_filter.contains_blocked_content(v)
        if is_blocked:
            raise ValueError(f"نص السياسة يحتوي على محتوى محظور")
        
        # فحص التكرار المفرط
        is_valid, reason = content_filter.check_repetitive_content(v)
        if not is_valid:
            raise ValueError(f"نص السياسة يحتوي على تكرار مفرط")
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "shop_name": "متجر الأزياء العصرية",
                "shop_specialization": "ملابس نسائية",
                "policy_type": "سياسات الاسترجاع و الاستبدال",
                "policy_text": "يحق للعميل إرجاع المنتج خلال 7 أيام من تاريخ الاستلام..."
            }
        }

class CriticalIssue(BaseModel):
    phrase: str = Field(..., description="العبارة المخالفة")
    severity: str = Field(..., description="درجة الخطورة")
    compliance_ratio: float = Field(..., ge=0, le=100, description="نسبة الامتثال")
    suggestion: str = Field(..., description="اقتراح للتحسين")
    legal_reference: Optional[str] = Field(None, description="المرجع النظامي")

class CompliancePoint(BaseModel):
    requirement: str = Field(..., description="المتطلب")
    status: str = Field(..., description="الحالة")
    found_text: Optional[str] = Field(None, description="النص المطابق")
    compliance_ratio: float = Field(..., ge=0, le=100)

class WeaknessPoint(BaseModel):
    issue: str = Field(..., description="المشكلة")
    exact_text: str = Field(..., description="النص بالضبط")
    compliance_ratio: float = Field(..., ge=0, le=100)
    suggestion: str = Field(..., description="اقتراح التحسين")
    legal_reference: str = Field(..., description="المرجع النظامي")

class AmbiguityPoint(BaseModel):
    missing_standard: str = Field(..., description="المعيار المفقود")
    description: str = Field(..., description="الوصف")
    importance: str = Field(..., description="الأهمية")
    suggested_text: str = Field(..., description="النص المقترح")

class PolicyMatchResult(BaseModel):
    is_matched: bool
    confidence: float = Field(..., ge=0, le=100)
    reason: str

class ComplianceReport(BaseModel):
    overall_compliance_ratio: float = Field(..., ge=0, le=100, description="نسبة الامتثال الكلية")
    compliance_grade: str = Field(..., description="تقييم الامتثال")
    critical_issues: List[CriticalIssue] = Field(default_factory=list)
    strengths: List[CompliancePoint] = Field(default_factory=list)
    weaknesses: List[WeaknessPoint] = Field(default_factory=list)
    ambiguities: List[AmbiguityPoint] = Field(default_factory=list)
    summary: str = Field(..., description="ملخص التقرير")
    recommendations: List[str] = Field(default_factory=list, description="توصيات عامة")
    
class ImprovementDetail(BaseModel):
    category: str = Field(..., description="نوع التحسين")
    description: str = Field(..., description="وصف التحسين")
    before: Optional[str] = Field(None, description="النص القديم")
    after: str = Field(..., description="النص الجديد")

class ImprovedPolicyResult(BaseModel):
    improved_policy: str = Field(..., description="النص الكامل للسياسة المحسّنة")
    improvements_made: List[ImprovementDetail] = Field(default_factory=list)
    compliance_enhancements: List[str] = Field(default_factory=list)
    structure_improvements: List[str] = Field(default_factory=list)
    estimated_new_compliance: float = Field(..., ge=0, le=100)
    key_additions: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(None, description="ملاحظات إضافية")

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    policy_match: Optional[PolicyMatchResult] = None
    compliance_report: Optional[ComplianceReport] = None
    improved_policy: Optional[ImprovedPolicyResult] = None  # جديد
    shop_name: str
    shop_specialization: str
    policy_type: PolicyType
    analysis_timestamp: str


class ComplianceEnhancement(BaseModel):
    before_ratio: float = Field(..., ge=0, le=100)
    after_ratio: float = Field(..., ge=0, le=100)
    improvement_percentage: float = Field(..., ge=0)

class PolicyComparisonResult(BaseModel):
    comparison_summary: str
    major_changes: List[Dict[str, Any]]
    compliance_improvement: Dict[str, Any]
    readability_score: Dict[str, Any]
    legal_coverage: Dict[str, Any]
    recommendations: List[str]

class RegenerationRequest(BaseModel):
    """طلب إعادة كتابة السياسة فقط"""
    shop_name: str = Field(..., min_length=2, max_length=200)
    shop_specialization: str = Field(..., min_length=2, max_length=200)
    policy_type: PolicyType
    original_policy: str = Field(..., min_length=50, max_length=50000)
    compliance_report: dict = Field(..., description="تقرير الامتثال")