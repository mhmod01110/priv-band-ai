"""
Policy Enhanced Validator
Rule-based policy matching to save AI tokens
"""
import re
from typing import Dict, List, Tuple, Optional
from app.logger import app_logger


class PolicyValidator:
    """
    Pre-AI validation and rule-based policy matching
    Saves tokens by catching obvious matches/mismatches
    """
    
    # Policy type keywords and patterns
    POLICY_RULES = {
        'سياسات الاسترجاع و الاستبدال': {
            'required_keywords': [
                'إرجاع', 'استرجاع', 'استبدال', 'إعادة', 'رد'
            ],
            'strong_indicators': [
                '7 أيام', 'سبعة أيام', 'أسبوع', 'فسخ العقد', 
                'استرداد المبلغ', 'استرداد القيمة'
            ],
            'moderate_indicators': [
                'منتج', 'بضاعة', 'سلعة', 'فاتورة', 'عيب', 
                'حالة أصلية', 'تغليف'
            ],
            'forbidden_topics': [
                'خصوصية', 'بيانات شخصية', 'حساب المستخدم',
                'شحن', 'توصيل', 'نقل'
            ],
            'minimum_length': 100,
            'expected_sections': [
                'مدة', 'شروط', 'استثناءات'
            ]
        },
        
        'سياسة الحساب و الخصوصية': {
            'required_keywords': [
                'خصوصية', 'بيانات', 'معلومات', 'حساب'
            ],
            'strong_indicators': [
                'بيانات شخصية', 'معلومات المستخدم', 'حماية البيانات',
                'حذف الحساب', 'تشفير', 'أمان'
            ],
            'moderate_indicators': [
                'اسم', 'عنوان', 'هاتف', 'بريد إلكتروني',
                'كلمة مرور', 'تسجيل', 'مشاركة'
            ],
            'forbidden_topics': [
                'إرجاع', 'استرجاع', 'استبدال',
                'شحن', 'توصيل'
            ],
            'minimum_length': 150,
            'expected_sections': [
                'جمع', 'استخدام', 'حماية', 'حقوق'
            ]
        },
        
        'سياسة الشحن و التوصيل': {
            'required_keywords': [
                'شحن', 'توصيل', 'نقل', 'إرسال'
            ],
            'strong_indicators': [
                'مدة التوصيل', 'رسوم الشحن', 'شركة الشحن',
                '15 يوماً', 'خمسة عشر يوماً', 'تأخير'
            ],
            'moderate_indicators': [
                'طلب', 'عنوان', 'منطقة', 'مجاني',
                'تتبع', 'استلام', 'تسليم'
            ],
            'forbidden_topics': [
                'إرجاع', 'استرجاع', 'استبدال',
                'خصوصية', 'بيانات شخصية'
            ],
            'minimum_length': 100,
            'expected_sections': [
                'مدة', 'تكلفة', 'مناطق'
            ]
        }
    }
    
    def __init__(self):
        self.confidence_thresholds = {
            'high': 0.85,      # Skip AI, direct accept
            'medium': 0.60,     # Use AI
            'low': 0.40,        # Use AI
            'very_low': 0.20   # Skip AI, direct reject
        }
    
    def validate_and_score(
        self,
        policy_text: str,
        policy_type: str
    ) -> Dict:
        """
        Main validation method
        
        Returns:
            {
                'confidence': float (0-1),
                'is_matched': bool,
                'reason': str,
                'skip_ai': bool,
                'details': dict
            }
        """
        app_logger.info(f"🔍 Policy Validator - Checking: {policy_type}")
        
        # Get rules for this policy type
        rules = self.POLICY_RULES.get(policy_type)
        if not rules:
            app_logger.warning(f"No rules found for policy type: {policy_type}")
            return {
                'confidence': 0.5,
                'is_matched': None,
                'reason': 'نوع سياسة غير معروف',
                'skip_ai': False,
                'details': {}
            }
        
        # Clean text
        text_lower = policy_text.lower().strip()
        
        # Calculate scores
        scores = self._calculate_scores(text_lower, rules)
        
        # Make decision
        decision = self._make_decision(scores, rules)
        
        app_logger.info(
            f"📊 Validation result - Confidence: {decision['confidence']:.2%}, "
            f"Skip AI: {decision['skip_ai']}"
        )
        
        return decision
    
    def _calculate_scores(self, text: str, rules: Dict) -> Dict:
        """
        Calculate various matching scores
        """
        scores = {
            'required_keywords': 0,
            'strong_indicators': 0,
            'moderate_indicators': 0,
            'forbidden_topics': 0,
            'length_check': 0,
            'section_check': 0
        }
        
        # 1. Required keywords (must have at least one)
        required = rules['required_keywords']
        found_required = sum(1 for kw in required if kw in text)
        scores['required_keywords'] = found_required / len(required) if required else 0
        
        # 2. Strong indicators (good to have)
        strong = rules['strong_indicators']
        found_strong = sum(1 for kw in strong if kw in text)
        scores['strong_indicators'] = found_strong / len(strong) if strong else 0
        
        # 3. Moderate indicators
        moderate = rules['moderate_indicators']
        found_moderate = sum(1 for kw in moderate if kw in text)
        scores['moderate_indicators'] = found_moderate / len(moderate) if moderate else 0
        
        # 4. Forbidden topics (should NOT be present)
        forbidden = rules['forbidden_topics']
        found_forbidden = sum(1 for kw in forbidden if kw in text)
        scores['forbidden_topics'] = found_forbidden / len(forbidden) if forbidden else 0
        
        # 5. Length check
        min_length = rules['minimum_length']
        scores['length_check'] = min(1.0, len(text) / min_length)
        
        # 6. Expected sections
        expected_sections = rules['expected_sections']
        found_sections = sum(1 for section in expected_sections if section in text)
        scores['section_check'] = found_sections / len(expected_sections) if expected_sections else 0
        
        return scores
    
    def _make_decision(self, scores: Dict, rules: Dict) -> Dict:
        """
        اتخاذ القرار النهائي بناءً على النسب
        """
        # حساب الثقة المرجحة
        if scores['required_keywords'] == 0:
            confidence = 0.1 + (scores['moderate_indicators'] * 0.1)
            return {
                'confidence': confidence,
                'is_matched': False,
                'reason': 'لا يحتوي النص على الكلمات الأساسية المطلوبة',
                'skip_ai': confidence < self.confidence_thresholds['very_low'],
                'details': scores
            }
        
        # فحص المواضيع المحظورة
        if scores['forbidden_topics'] > 0.5:
            confidence = 0.2
            return {
                'confidence': confidence,
                'is_matched': False,
                'reason': 'النص يحتوي على مواضيع لا تتعلق بنوع السياسة المحدد',
                'skip_ai': True,
                'details': scores
            }
        
        # حساب الثقة النهائية
        weights = {
            'required_keywords': 0.35,
            'strong_indicators': 0.25,
            'moderate_indicators': 0.15,
            'length_check': 0.10,
            'section_check': 0.15
        }
        
        confidence = sum(
            scores.get(key, 0) * weight
            for key, weight in weights.items()
        )
        
        # عقوبة للمواضيع المحظورة
        confidence *= (1 - scores['forbidden_topics'] * 0.5)
        
        # ✅ المنطق الصحيح - محاذي مع Stage 1 (30-70%)
        skip_ai = False
        is_matched = None
        reason = ''
        
        # الحالة 1: نسبة عالية (>= 70%)
        if confidence >= 0.70:
            is_matched = True  # ✅ متأكد إنها matched
            
            if confidence >= 0.85:
                # واثق جدًا - نتخطى AI تمامًا
                skip_ai = True
                reason = 'تطابق قوي - النص يحتوي على جميع المؤشرات المطلوبة'
            else:
                # واثق بس مش جدًا - هنأكد في Stage 3 بدون Stage 1
                skip_ai = False
                reason = 'تطابق جيد - تم التحقق بالقواعد المحلية'
        
        # الحالة 2: نسبة منخفضة (<= 30%)
        elif confidence <= 0.30:
            is_matched = False  # ✅ متأكد إنها مش matched
            
            if confidence <= 0.20:
                # واثق جدًا إنها غلط - نتخطى AI تمامًا
                skip_ai = True
                reason = 'عدم تطابق واضح - النص لا يحتوي على المؤشرات الكافية'
            else:
                # شبه متأكد إنها غلط - هنأكد في Stage 3 بدون Stage 1
                skip_ai = False
                reason = 'تطابق ضعيف - تم التحقق بالقواعد المحلية'
        
        # الحالة 3: نسبة غامضة (30-70%) ← المنطقة الوحيدة لـ None
        else:  # 30% < confidence < 70%
            is_matched = None  # ❓ مش متأكد - محتاج AI في Stage 1
            skip_ai = False
            reason = 'يحتاج تحليل إضافي بواسطة الذكاء الاصطناعي'
        
        return {
            'confidence': confidence,
            'is_matched': is_matched,
            'reason': reason,
            'skip_ai': skip_ai,
            'details': scores
        }
    
    def get_missing_elements(
        self,
        policy_text: str,
        policy_type: str
    ) -> List[str]:
        """
        Get list of missing important elements
        """
        rules = self.POLICY_RULES.get(policy_type, {})
        text_lower = policy_text.lower()
        
        missing = []
        
        # Check required keywords
        for kw in rules.get('required_keywords', []):
            if kw not in text_lower:
                missing.append(f"كلمة مفتاحية مفقودة: {kw}")
        
        # Check strong indicators
        found_strong = sum(
            1 for kw in rules.get('strong_indicators', [])
            if kw in text_lower
        )
        if found_strong == 0:
            missing.append("لا يحتوي على مؤشرات قوية للنوع المطلوب")
        
        # Check minimum length
        if len(policy_text) < rules.get('minimum_length', 100):
            missing.append(
                f"النص قصير جداً (الحد الأدنى: {rules.get('minimum_length')} حرف)"
            )
        
        return missing


def rule_based_policy_match(
    policy_type: str,
    policy_text: str
) -> Dict:
    """
    Standalone function for rule-based matching
    Used for graceful degradation when AI is unavailable
    """
    validator = PolicyValidator()
    result = validator.validate_and_score(policy_text, policy_type)
    
    return {
        'is_matched': result['is_matched'] or result['confidence'] > 0.6,
        'confidence': result['confidence'] * 100,  # Convert to percentage
        'reason': result['reason'],
        'method': 'rule_based',
        'details': result['details']
    }


def enhanced_policy_validation(
    policy_type: str,
    policy_text: str
) -> Tuple[bool, Dict]:
    """
    Enhanced Policy validation
    
    Returns:
        (should_use_ai, validation_result)
    """
    validator = PolicyValidator()
    result = validator.validate_and_score(policy_text, policy_type)
    
    should_use_ai = not result['skip_ai']
    
    app_logger.info(
        f"📋 Enhanced validation - Use AI: {should_use_ai}, "
        f"Confidence: {result['confidence']:.2%}"
    )
    
    return should_use_ai, result


# Pre-validation checks (before task creation)
def pre_validate_input(
    policy_text: str,
    policy_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Quick pre-validation before creating Celery task
    
    Returns:
        (is_valid, error_message)
    """
    # Length check
    if len(policy_text) < 50:
        return False, "نص السياسة قصير جداً (الحد الأدنى 50 حرف)"
    
    if len(policy_text) > 50000:
        return False, "نص السياسة طويل جداً (الحد الأقصى 50,000 حرف)"
    
    # Basic content check
    if not policy_text.strip():
        return False, "نص السياسة فارغ"
    
    # Check for meaningful content (not just spaces/symbols)
    words = re.findall(r'\w+', policy_text)
    if len(words) < 20:
        return False, "النص لا يحتوي على محتوى كافٍ (الحد الأدنى 20 كلمة)"
    
    # Check for Arabic content
    arabic_chars = re.findall(r'[\u0600-\u06FF]', policy_text)
    if len(arabic_chars) < 30:
        return False, "النص يجب أن يحتوي على محتوى عربي كافٍ"
    
    return True, None