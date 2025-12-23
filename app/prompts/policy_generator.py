"""
Policy Generator - Stage 4
إعادة كتابة السياسة بنسخة محسّنة ممتثلة
"""

def get_policy_regeneration_prompt(
    shop_name: str,
    shop_specialization: str,
    policy_type: str,
    original_policy_text: str,
    compliance_report: dict
) -> str:
    """
    إنشاء Prompt لإعادة كتابة السياسة بنسخة محسّنة
    
    Args:
        shop_name: اسم المتجر
        shop_specialization: تخصص المتجر
        policy_type: نوع السياسة
        original_policy_text: النص الأصلي
        compliance_report: تقرير الامتثال الكامل
    
    Returns:
        Prompt لإعادة الكتابة
    """
    
    # استخراج المعلومات من التقرير
    overall_compliance = compliance_report.get('overall_compliance_ratio', 0)
    compliance_grade = compliance_report.get('compliance_grade', 'غير محدد')
    critical_issues = compliance_report.get('critical_issues', [])
    weaknesses = compliance_report.get('weaknesses', [])
    ambiguities = compliance_report.get('ambiguities', [])
    strengths = compliance_report.get('strengths', [])
    
    # بناء قائمة المشاكل الحرجة
    critical_text = ""
    if critical_issues:
        critical_text = "### المشاكل الحرجة التي يجب إصلاحها:\n"
        for i, issue in enumerate(critical_issues, 1):
            critical_text += f"{i}. **العبارة المخالفة:** \"{issue['phrase']}\"\n"
            critical_text += f"   - **المشكلة:** {issue['severity']}\n"
            critical_text += f"   - **الاقتراح:** {issue['suggestion']}\n"
            critical_text += f"   - **المرجع:** {issue.get('legal_reference', 'N/A')}\n\n"
    
    # بناء قائمة نقاط الضعف
    weaknesses_text = ""
    if weaknesses:
        weaknesses_text = "### نقاط الضعف التي يجب تحسينها:\n"
        for i, weakness in enumerate(weaknesses, 1):
            weaknesses_text += f"{i}. **المشكلة:** {weakness['issue']}\n"
            weaknesses_text += f"   - **النص الحالي:** \"{weakness['exact_text']}\"\n"
            weaknesses_text += f"   - **الاقتراح:** {weakness['suggestion']}\n"
            weaknesses_text += f"   - **المرجع:** {weakness['legal_reference']}\n\n"
    
    # بناء قائمة المعايير المفقودة
    missing_text = ""
    if ambiguities:
        missing_text = "### المعايير المفقودة التي يجب إضافتها:\n"
        for i, ambiguity in enumerate(ambiguities, 1):
            missing_text += f"{i}. **المعيار:** {ambiguity['missing_standard']}\n"
            missing_text += f"   - **الوصف:** {ambiguity['description']}\n"
            missing_text += f"   - **الأهمية:** {ambiguity['importance']}\n"
            missing_text += f"   - **النص المقترح:** \"{ambiguity['suggested_text']}\"\n\n"
    
    # بناء قائمة نقاط القوة
    strengths_text = ""
    if strengths:
        strengths_text = "### نقاط القوة (يجب الحفاظ عليها):\n"
        for i, strength in enumerate(strengths, 1):
            strengths_text += f"{i}. **{strength['requirement']}** - {strength['status']}\n"
            if strength.get('found_text'):
                strengths_text += f"   - النص: \"{strength['found_text']}\"\n"
    
    prompt = f"""أنت محلل قانوني وكاتب سياسات محترف متخصص في قوانين التجارة الإلكترونية السعودية.

## المهمة:
إعادة كتابة سياسة "{policy_type}" لـ "{shop_name}" بنسخة محسّنة ممتثلة بالكامل للقوانين السعودية.

## معلومات المتجر:
- **اسم المتجر:** {shop_name}
- **التخصص:** {shop_specialization}
- **نوع السياسة:** {policy_type}

## التقييم الحالي:
- **نسبة الامتثال:** {overall_compliance}%
- **التقييم:** {compliance_grade}
- **عدد المشاكل الحرجة:** {len(critical_issues)}
- **عدد نقاط الضعف:** {len(weaknesses)}
- **عدد المعايير المفقودة:** {len(ambiguities)}

---

## النص الأصلي:
```
{original_policy_text}
```

---

{critical_text}

{weaknesses_text}

{missing_text}

{strengths_text}

---

## إرشادات إعادة الكتابة:

### 1. الأسلوب:
- استخدم لغة عربية واضحة وسهلة الفهم
- تجنب المصطلحات القانونية المعقدة إلا عند الضرورة
- اكتب بأسلوب ودود ومحترف
- استخدم تنسيق منظم (عناوين، نقاط، فقرات)

### 2. المحتوى:
- أصلح جميع المشاكل الحرجة المذكورة أعلاه
- حسّن جميع نقاط الضعف
- أضف جميع المعايير المفقودة
- احتفظ بنقاط القوة الموجودة
- تأكد من الامتثال الكامل للقوانين السعودية

### 3. التنظيم:
- استخدم عناوين رئيسية وفرعية واضحة
- رقّم النقاط المهمة
- ميّز المعلومات الحرجة
- أضف أمثلة توضيحية عند الحاجة

### 4. التخصيص:
- خصص السياسة لتناسب تخصص المتجر ({shop_specialization})
- أضف استثناءات مناسبة إذا لزم الأمر
- استخدم أمثلة ذات صلة بنشاط المتجر

### 5. الشمولية:
- تأكد من تغطية جميع المتطلبات القانونية
- لا تحذف أي معلومة مهمة من النص الأصلي
- أضف التفاصيل المفقودة

---

## المخرج المطلوب:

قدم الإجابة بصيغة JSON فقط بدون أي نص إضافي:

{{
  "improved_policy": "النص الكامل للسياسة المحسّنة",
  "improvements_made": [
    {{
      "category": "تصحيح مشكلة حرجة" أو "تحسين نقطة ضعف" أو "إضافة معيار مفقود",
      "description": "وصف التحسين",
      "before": "النص القديم (إن وجد)",
      "after": "النص الجديد"
    }}
  ],
  "compliance_enhancements": [
    "تحسين 1: وصف كيف تم تحسين الامتثال",
    "تحسين 2: ...",
    "تحسين 3: ..."
  ],
  "structure_improvements": [
    "تحسين في التنظيم 1",
    "تحسين في التنظيم 2"
  ],
  "estimated_new_compliance": 95,
  "key_additions": [
    "إضافة مهمة 1",
    "إضافة مهمة 2"
  ],
  "notes": "أي ملاحظات إضافية للمتجر"
}}

---

**ملاحظة مهمة:** السياسة المحسّنة يجب أن تكون جاهزة للاستخدام مباشرة، احترافية، وممتثلة بنسبة 95%+ للقوانين السعودية.
"""
    
    return prompt


def get_policy_comparison_prompt(
    original_policy: str,
    improved_policy: str,
    policy_type: str
) -> str:
    """
    إنشاء Prompt لمقارنة النسخة الأصلية بالمحسّنة
    
    Args:
        original_policy: النص الأصلي
        improved_policy: النص المحسّن
        policy_type: نوع السياسة
    
    Returns:
        Prompt للمقارنة
    """
    
    prompt = f"""أنت محلل قانوني متخصص. قم بمقارنة النسختين من سياسة "{policy_type}".

## النسخة الأصلية:
```
{original_policy}
```

## النسخة المحسّنة:
```
{improved_policy}
```

---

قدم مقارنة تفصيلية بصيغة JSON:

{{
  "comparison_summary": "ملخص المقارنة بين النسختين",
  "major_changes": [
    {{
      "change_type": "إضافة" أو "تعديل" أو "حذف",
      "description": "وصف التغيير",
      "original": "النص الأصلي",
      "improved": "النص المحسّن",
      "impact": "تأثير هذا التغيير على الامتثال"
    }}
  ],
  "compliance_improvement": {{
    "estimated_before": 70,
    "estimated_after": 95,
    "improvement_percentage": 25
  }},
  "readability_score": {{
    "before": 6,
    "after": 9,
    "comment": "تحسنت الوضوح والتنظيم"
  }},
  "legal_coverage": {{
    "before": ["متطلب 1", "متطلب 2"],
    "after": ["متطلب 1", "متطلب 2", "متطلب 3", "متطلب 4"],
    "added_coverage": ["متطلب 3", "متطلب 4"]
  }},
  "recommendations": [
    "توصية إضافية 1",
    "توصية إضافية 2"
  ]
}}
"""
    
    return prompt
