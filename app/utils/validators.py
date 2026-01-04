"""
Input Validators
Pre-processing validation functions
"""
from typing import Dict, Optional, Tuple
from app.safeguards import input_sanitizer, content_filter
from app.logger import app_logger


def validate_input_before_processing(
    shop_name: str,
    shop_specialization: str,
    policy_text: str,
    task_id: str = "unknown"
) -> Tuple[bool, Optional[Dict]]:
    """
    Pre-stage validation using safeguards
    
    Validates all input data before processing to catch issues early
    and provide clear error messages to users.
    
    Args:
        shop_name: Name of the shop
        shop_specialization: Shop specialization/category
        policy_text: The policy text to validate
        task_id: Task ID for logging (optional)
    
    Returns:
        Tuple of (is_valid, error_response)
        - is_valid: True if validation passed, False otherwise
        - error_response: None if valid, dict with error details if invalid
    """
    app_logger.info(f"🔒 [Task {task_id}] Running pre-stage input validation")
    
    # 1. Length validation
    is_valid, error_msg = input_sanitizer.validate_text_length(policy_text, "نص السياسة")
    if not is_valid:
        app_logger.warning(f"❌ [Task {task_id}] Length validation failed: {error_msg}")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'length_error',
            'message': 'خطأ في طول النص',
            'details': error_msg,
            'stage': 'pre_validation',
            'user_action': 'يرجى التأكد من أن النص يحتوي على 50 حرف على الأقل ولا يتجاوز 50,000 حرف'
        }
    
    # 2. Suspicious content check
    is_safe, reason = input_sanitizer.check_suspicious_content(policy_text)
    if not is_safe:
        app_logger.warning(f"❌ [Task {task_id}] Suspicious content detected: {reason}")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'suspicious_content',
            'message': 'تم اكتشاف محتوى مشبوه',
            'details': reason,
            'stage': 'pre_validation',
            'user_action': 'يرجى إزالة أي أكواد برمجية أو محتوى غير قانوني من النص'
        }
    
    # 3. Blocked content check
    is_blocked, reason = content_filter.contains_blocked_content(policy_text)
    if is_blocked:
        app_logger.warning(f"❌ [Task {task_id}] Blocked content detected: {reason}")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'blocked_content',
            'message': 'تم اكتشاف محتوى محظور',
            'details': 'النص يحتوي على كلمات أو عبارات غير مسموح بها',
            'stage': 'pre_validation',
            'user_action': 'يرجى مراجعة النص وإزالة أي محتوى غير ملائم'
        }
    
    # 4. Repetitive content check (spam detection)
    is_valid, reason = content_filter.check_repetitive_content(policy_text)
    if not is_valid:
        app_logger.warning(f"❌ [Task {task_id}] Repetitive content detected")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'spam_detected',
            'message': 'تم اكتشاف تكرار مفرط في النص',
            'details': 'النص يحتوي على تكرار غير طبيعي لنفس الكلمات أو العبارات',
            'stage': 'pre_validation',
            'user_action': 'يرجى تقديم نص حقيقي وليس محتوى مكرر أو عشوائي'
        }
    
    # 5. Shop name validation
    shop_name_clean = input_sanitizer.sanitize_text(shop_name)
    if len(shop_name_clean) < 2:
        app_logger.warning(f"❌ [Task {task_id}] Shop name too short")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'invalid_shop_name',
            'message': 'اسم المتجر غير صالح',
            'details': 'اسم المتجر قصير جداً أو يحتوي على أحرف غير صالحة',
            'stage': 'pre_validation',
            'user_action': 'يرجى إدخال اسم متجر صحيح (حرفان على الأقل)'
        }
    
    # 6. Specialization validation
    specialization_clean = input_sanitizer.sanitize_text(shop_specialization)
    if len(specialization_clean) < 2:
        app_logger.warning(f"❌ [Task {task_id}] Specialization too short")
        return False, {
            'success': False,
            'error_type': 'validation_error',
            'error_category': 'invalid_specialization',
            'message': 'تخصص المتجر غير صالح',
            'details': 'تخصص المتجر قصير جداً أو يحتوي على أحرف غير صالحة',
            'stage': 'pre_validation',
            'user_action': 'يرجى إدخال تخصص المتجر بشكل صحيح'
        }
    
    app_logger.info(f"✅ [Task {task_id}] Pre-stage validation passed")
    return True, None


def validate_compliance_report_structure(response: Dict) -> bool:
    """
    التحقق من بنية الاستجابة JSON لتقرير الامتثال
    
    Args:
        response: Dictionary containing the compliance report
    
    Returns:
        True if structure is valid, False otherwise
    """
    required_fields = [
        'overall_compliance_ratio',
        'compliance_grade',
        'critical_issues',
        'strengths',
        'weaknesses',
        'ambiguities',
        'summary',
        'recommendations'
    ]
    
    # التحقق من وجود الحقول الأساسية
    for field in required_fields:
        if field not in response:
            app_logger.error(f"❌ حقل مفقود: {field}")
            return False
    
    # التحقق من نوع البيانات
    if not isinstance(response['overall_compliance_ratio'], (int, float)):
        app_logger.error("❌ overall_compliance_ratio يجب أن يكون رقماً")
        return False
    
    if not 0 <= response['overall_compliance_ratio'] <= 100:
        app_logger.error("❌ overall_compliance_ratio يجب أن يكون بين 0 و 100")
        return False
    
    # التحقق من compliance_grade
    valid_grades = ["ممتاز", "جيد جداً", "جيد", "مقبول", "ضعيف", "غير ممتثل"]
    if response['compliance_grade'] not in valid_grades:
        app_logger.error(f"❌ compliance_grade غير صحيح: {response['compliance_grade']}")
        return False
    
    # التحقق من المصفوفات
    for field in ['critical_issues', 'strengths', 'weaknesses', 'ambiguities']:
        if not isinstance(response[field], list):
            app_logger.error(f"❌ {field} يجب أن يكون مصفوفة")
            return False
    
    # التحقق من recommendations
    if not isinstance(response['recommendations'], list):
        app_logger.error("❌ recommendations يجب أن يكون مصفوفة")
        return False
    
    for rec in response['recommendations']:
        if not isinstance(rec, str):
            app_logger.error("❌ كل توصية يجب أن تكون نص (string)")
            return False
    
    # التحقق من بنية critical_issues
    for issue in response['critical_issues']:
        required_issue_fields = ['phrase', 'severity', 'compliance_ratio', 
                                'suggestion', 'legal_reference']
        for field in required_issue_fields:
            if field not in issue:
                app_logger.error(f"❌ حقل مفقود في critical_issues: {field}")
                return False
    
    # التحقق من بنية strengths
    for strength in response['strengths']:
        required_strength_fields = ['requirement', 'status', 'found_text', 
                                   'compliance_ratio']
        for field in required_strength_fields:
            if field not in strength:
                app_logger.error(f"❌ حقل مفقود في strengths: {field}")
                return False
    
    # التحقق من بنية weaknesses
    for weakness in response['weaknesses']:
        required_weakness_fields = ['issue', 'exact_text', 'compliance_ratio', 
                                   'suggestion', 'legal_reference']
        for field in required_weakness_fields:
            if field not in weakness:
                app_logger.error(f"❌ حقل مفقود في weaknesses: {field}")
                return False
    
    # التحقق من بنية ambiguities
    for ambiguity in response['ambiguities']:
        required_ambiguity_fields = ['missing_standard', 'description', 
                                    'importance', 'suggested_text']
        for field in required_ambiguity_fields:
            if field not in ambiguity:
                app_logger.error(f"❌ حقل مفقود في ambiguities: {field}")
                return False
    
    app_logger.info("✅ البنية صحيحة 100%")
    return True