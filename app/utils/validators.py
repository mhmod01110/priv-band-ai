import json
from typing import Dict, Any

def validate_compliance_report_structure(response: Dict[str, Any]) -> bool:
    """
    التحقق من بنية الاستجابة JSON
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
            print(f"❌ حقل مفقود: {field}")
            return False
    
    # التحقق من نوع البيانات
    if not isinstance(response['overall_compliance_ratio'], (int, float)):
        print("❌ overall_compliance_ratio يجب أن يكون رقماً")
        return False
    
    if not 0 <= response['overall_compliance_ratio'] <= 100:
        print("❌ overall_compliance_ratio يجب أن يكون بين 0 و 100")
        return False
    
    # التحقق من compliance_grade
    valid_grades = ["ممتاز", "جيد جداً", "جيد", "مقبول", "ضعيف", "غير ممتثل"]
    if response['compliance_grade'] not in valid_grades:
        print(f"❌ compliance_grade غير صحيح: {response['compliance_grade']}")
        return False
    
    # التحقق من المصفوفات
    for field in ['critical_issues', 'strengths', 'weaknesses', 'ambiguities']:
        if not isinstance(response[field], list):
            print(f"❌ {field} يجب أن يكون مصفوفة")
            return False
    
    # التحقق من recommendations
    if not isinstance(response['recommendations'], list):
        print("❌ recommendations يجب أن يكون مصفوفة")
        return False
    
    for rec in response['recommendations']:
        if not isinstance(rec, str):
            print("❌ كل توصية يجب أن تكون نص (string)")
            return False
    
    # التحقق من بنية critical_issues
    for issue in response['critical_issues']:
        required_issue_fields = ['phrase', 'severity', 'compliance_ratio', 
                                'suggestion', 'legal_reference']
        for field in required_issue_fields:
            if field not in issue:
                print(f"❌ حقل مفقود في critical_issues: {field}")
                return False
    
    # التحقق من بنية strengths
    for strength in response['strengths']:
        required_strength_fields = ['requirement', 'status', 'found_text', 
                                   'compliance_ratio']
        for field in required_strength_fields:
            if field not in strength:
                print(f"❌ حقل مفقود في strengths: {field}")
                return False
    
    # التحقق من بنية weaknesses
    for weakness in response['weaknesses']:
        required_weakness_fields = ['issue', 'exact_text', 'compliance_ratio', 
                                   'suggestion', 'legal_reference']
        for field in required_weakness_fields:
            if field not in weakness:
                print(f"❌ حقل مفقود في weaknesses: {field}")
                return False
    
    # التحقق من بنية ambiguities
    for ambiguity in response['ambiguities']:
        required_ambiguity_fields = ['missing_standard', 'description', 
                                    'importance', 'suggested_text']
        for field in required_ambiguity_fields:
            if field not in ambiguity:
                print(f"❌ حقل مفقود في ambiguities: {field}")
                return False
    
    print("✅ البنية صحيحة 100%")
    return True