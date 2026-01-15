from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
# نقوم باستيراد input_sanitizer داخل الدوال لتجنب Circular Import إذا كان safeguards يستورد models

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
        from app.safeguards import input_sanitizer
        
        # استخدام دالة التنظيف الموحدة
        v = input_sanitizer.sanitize_text(v)
        
        # فحص الأحرف الخاصة المشبوهة (XSS prevention basic)
        suspicious_chars = ['<', '>', '{', '}', '[', ']', '\\', '|', ';']
        if any(char in v for char in suspicious_chars):
            raise ValueError("اسم المتجر يحتوي على أحرف غير مسموحة")
        
        return v
    
    @field_validator('shop_specialization')
    @classmethod
    def validate_specialization(cls, v: str) -> str:
        """التحقق من تخصص المتجر"""
        from app.safeguards import input_sanitizer
        
        # استخدام دالة التنظيف الموحدة
        v = input_sanitizer.sanitize_text(v)
        
        suspicious_chars = ['<', '>', '{', '}', '[', ']', '\\', '|', ';']
        if any(char in v for char in suspicious_chars):
            raise ValueError("تخصص المتجر يحتوي على أحرف غير مسموحة")
        
        return v
    
    @field_validator('policy_text')
    @classmethod
    def validate_policy_text(cls, v: str) -> str:
        """التحقق من نص السياسة"""
        # استيراد محلي لتجنب Circular Import
        from app.safeguards import input_sanitizer, content_filter
        
        # 1. تنظيف النص
        v = input_sanitizer.sanitize_text(v)
        
        # 2. فحص المحتوى المشبوه (XSS, Injection)
        is_safe, reason = input_sanitizer.check_suspicious_content(v)
        if not is_safe:
            # الرسالة هنا ستظهر في الـ Frontend بفضل التعديل الأخير في app.js
            raise ValueError(f"نص السياسة يحتوي على محتوى مشبوه: {reason}")
        
        # 3. فحص المحتوى المحظور (Keywords)
        is_blocked, reason = content_filter.contains_blocked_content(v)
        if is_blocked:
            raise ValueError(f"نص السياسة يحتوي على محتوى محظور: {reason}")
        
        # 4. فحص التكرار المفرط (Spam)
        is_valid, reason = content_filter.check_repetitive_content(v)
        if not is_valid:
            raise ValueError(f"نص السياسة يحتوي على تكرار مفرط للنصوص (Spam)")
        
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

class ForceNewAnalysisRequest(PolicyAnalysisRequest):
    idempotency_key: str = Field(
      ..., 
      min_length=32,  # SHA256 hash length
      max_length=200,
      description="مفتاح التحليل الفريد من الطلب السابق"
  )
    @field_validator('idempotency_key')
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
      """التحقق من صحة idempotency_key"""
      # إزالة المسافات الزائدة
      v = v.strip()
      
      # التحقق من format: "idempotency:HASH"
      if not v.startswith("idempotency:"):
          raise ValueError("مفتاح التحليل يجب أن يبدأ بـ 'idempotency:'")
      
      # استخراج الـ hash part
      hash_part = v.replace("idempotency:", "", 1)
      
      # التحقق من أن الـ hash يحتوي على hex characters فقط
      if not hash_part or not all(c in '0123456789abcdefABCDEF' for c in hash_part):
          raise ValueError("مفتاح التحليل غير صالح - يجب أن يكون hash hex صحيح")
      
      # التحقق من طول الـ hash (SHA256 = 64 حرف)
      if len(hash_part) != 64:
          raise ValueError("مفتاح التحليل غير صالح - الطول غير صحيح")
      
      return v  # إرجاع الـ key كما هو (مع prefix)
      
    class Config:
        json_schema_extra = {
            "example": {
                "idempotency_key": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
                "shop_name": "متجر الأزياء العصرية",
                "shop_specialization": "ملابس نسائية",
                "policy_type": "سياسات الاسترجاع و الاستبدال",
                "policy_text": "يحق للعميل إرجاع المنتج خلال 7 أيام من تاريخ الاستلام..."
            }
        }  
# --- باقي الموديلات كما هي، مع تعديل AnalysisResponse ---

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
    improved_policy: Optional[ImprovedPolicyResult] = None
    shop_name: str
    shop_specialization: str
    policy_type: PolicyType
    analysis_timestamp: str
    # تمت إضافة هذا الحقل ليتوافق مع tasks.py في حالة وجود تحذيرات غير حرجة
    warnings: Optional[List[str]] = Field(default=None, description="تحذيرات النظام") 

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