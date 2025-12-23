# 📝 دليل نظام Logging - Legal Policy Analyzer

## نظرة عامة

نظام Logging متقدم وشامل يسجل جميع العمليات في التطبيق بما في ذلك:
- جميع الـ Prompts المرسلة إلى OpenAI
- جميع الاستجابات من OpenAI
- الأخطاء والمشاكل
- إحصائيات التحليل
- معلومات الأداء

---

## 📂 هيكل مجلد Logs

```
logs/
├── app.log                           # Log عام للتطبيق
├── prompts/                          # جميع الـ Prompts
│   ├── 20241214_153045_stage1_match_متجر_الأزياء.txt
│   ├── 20241214_153050_stage2_analyze_متجر_الأزياء.txt
│   └── ...
├── responses/                        # جميع الاستجابات
│   ├── 20241214_153045_stage1_match_متجر_الأزياء.json
│   ├── 20241214_153050_stage2_analyze_متجر_الأزياء.json
│   └── ...
├── errors/                          # سجلات الأخطاء
│   ├── errors_20241214.log
│   ├── error_20241214_153100.json
│   └── ...
└── analytics/                       # الإحصائيات اليومية
    ├── analytics_20241214.jsonl
    └── ...
```

---

## 🎨 أنواع Logs

### 1. Console Logs (ملونة)
تظهر في Terminal أثناء التشغيل:

```
🚀 2024-12-14 15:30:45 - legal_policy_analyzer - INFO - Starting new analysis
📝 2024-12-14 15:30:46 - legal_policy_analyzer - INFO - Prompt logged: stage1_match
✅ 2024-12-14 15:30:50 - legal_policy_analyzer - INFO - Policy matched - Confidence: 95.5%
📊 2024-12-14 15:31:15 - legal_policy_analyzer - INFO - Analysis completed
```

الألوان:
- 🔵 **DEBUG** - Cyan
- 🟢 **INFO** - Green
- 🟡 **WARNING** - Yellow
- 🔴 **ERROR** - Red
- 🟣 **CRITICAL** - Magenta

### 2. File Logs
جميع التفاصيل تُحفظ في ملفات للرجوع إليها لاحقاً.

---

## 📋 محتوى Logs

### Prompt Log Files
ملف `.txt` لكل Prompt يحتوي على:

```
================================================================================
PROMPT METADATA
================================================================================
{
  "timestamp": "2024-12-14T15:30:45.123456",
  "stage": "stage1_match",
  "shop_name": "متجر الأزياء العصرية",
  "policy_type": "سياسات الاسترجاع و الاستبدال",
  "prompt_length": 2456,
  "metadata": {
    "policy_text_length": 850
  }
}

================================================================================
PROMPT CONTENT
================================================================================
أنت خبير في تحليل السياسات القانونية...
[النص الكامل للـ Prompt]
```

### Response Log Files
ملف `.json` لكل استجابة:

```json
{
  "timestamp": "2024-12-14T15:30:50.123456",
  "stage": "stage2_analyze",
  "shop_name": "متجر الأزياء العصرية",
  "policy_type": "سياسات الاسترجاع و الاستبدال",
  "response": {
    "overall_compliance_ratio": 78.5,
    "compliance_grade": "جيد",
    "critical_issues": [...],
    "strengths": [...],
    "weaknesses": [...],
    "ambiguities": [...],
    "summary": "...",
    "recommendations": [...]
  },
  "metadata": {
    "overall_compliance": 78.5,
    "critical_issues_count": 2
  }
}
```

### Analytics Log Files
ملف `.jsonl` (JSON Lines) يومي للإحصائيات:

```json
{"timestamp": "2024-12-14T15:30:45", "shop_name": "متجر 1", "compliance_ratio": 78.5, "duration_seconds": 25.3, "success": true}
{"timestamp": "2024-12-14T16:45:20", "shop_name": "متجر 2", "compliance_ratio": 85.2, "duration_seconds": 22.1, "success": true}
{"timestamp": "2024-12-14T17:20:10", "shop_name": "متجر 3", "compliance_ratio": 0, "duration_seconds": 5.2, "success": false}
```

### Error Log Files
ملفات JSON للأخطاء:

```json
{
  "timestamp": "2024-12-14T15:30:55.123456",
  "error_type": "JSONDecodeError",
  "error_message": "Expecting value: line 1 column 1 (char 0)",
  "shop_name": "متجر الأزياء",
  "traceback": "Traceback (most recent call last):\n  File..."
}
```

---

## 🔍 استخدام Logger في الكود

### استيراد Logger

```python
from app.logger import app_logger
```

### Logging أساسي

```python
# رسائل بسيطة
app_logger.debug("رسالة تصحيح")
app_logger.info("رسالة معلومات")
app_logger.warning("تحذير")
app_logger.error("خطأ")
app_logger.critical("خطأ حرج")
```

### Logging Prompts

```python
app_logger.log_prompt(
    stage="stage1_match",
    shop_name="متجر الأزياء",
    policy_type="سياسات الاسترجاع و الاستبدال",
    prompt=prompt_text,
    metadata={
        "policy_text_length": len(policy_text),
        "custom_field": "value"
    }
)
```

### Logging Responses

```python
app_logger.log_response(
    stage="stage2_analyze",
    shop_name="متجر الأزياء",
    policy_type="سياسات الاسترجاع و الاستبدال",
    response=response_dict,
    metadata={
        "overall_compliance": 78.5,
        "critical_issues_count": 2
    }
)
```

### Logging Analysis Summary

```python
app_logger.log_analysis_summary(
    shop_name="متجر الأزياء",
    policy_type="سياسات الاسترجاع و الاستبدال",
    compliance_ratio=78.5,
    duration=25.3,
    success=True
)
```

### Logging Errors

```python
import traceback

try:
    # some code
    pass
except Exception as e:
    app_logger.log_error(
        error_type=type(e).__name__,
        error_message=str(e),
        shop_name="متجر الأزياء",
        traceback_info=traceback.format_exc()
    )
```

---

## 📊 تحليل Logs

### قراءة إحصائيات يومية

```python
import json

# قراءة ملف analytics
with open('logs/analytics/analytics_20241214.jsonl', 'r', encoding='utf-8') as f:
    analyses = [json.loads(line) for line in f]

# حساب متوسط نسبة الامتثال
avg_compliance = sum(a['compliance_ratio'] for a in analyses if a['success']) / len(analyses)
print(f"Average Compliance: {avg_compliance}%")

# عدد التحليلات الناجحة
successful = sum(1 for a in analyses if a['success'])
print(f"Successful Analyses: {successful}/{len(analyses)}")

# متوسط المدة الزمنية
avg_duration = sum(a['duration_seconds'] for a in analyses) / len(analyses)
print(f"Average Duration: {avg_duration:.2f} seconds")
```

### البحث في Prompts

```python
from pathlib import Path
import re

# البحث عن جميع prompts لمتجر معين
shop_name = "متجر_الأزياء"
prompts_dir = Path("logs/prompts")

shop_prompts = list(prompts_dir.glob(f"*{shop_name}*.txt"))
print(f"Found {len(shop_prompts)} prompts for {shop_name}")

for prompt_file in shop_prompts:
    print(f"- {prompt_file.name}")
```

### تحليل الأخطاء

```python
from pathlib import Path
import json
from collections import Counter

errors_dir = Path("logs/errors")
error_files = errors_dir.glob("error_*.json")

error_types = []
for error_file in error_files:
    with open(error_file, 'r', encoding='utf-8') as f:
        error_data = json.load(f)
        error_types.append(error_data['error_type'])

# عرض أكثر الأخطاء شيوعاً
error_counts = Counter(error_types)
print("Most common errors:")
for error_type, count in error_counts.most_common(5):
    print(f"  {error_type}: {count} times")
```

---

## ⚙️ تخصيص Logger

### تغيير مستوى Logging

```python
# في app/logger.py
self.logger.setLevel(logging.DEBUG)  # عرض كل شيء
self.logger.setLevel(logging.INFO)   # عرض INFO وما فوق
self.logger.setLevel(logging.WARNING) # عرض تحذيرات وأخطاء فقط
```

### إضافة Handler جديد

```python
# في app/logger.py في _setup_handlers()

# مثال: Handler للإرسال عبر البريد للأخطاء الحرجة
import logging.handlers

smtp_handler = logging.handlers.SMTPHandler(
    mailhost=('smtp.example.com', 587),
    fromaddr='app@example.com',
    toaddrs=['admin@example.com'],
    subject='Legal Analyzer Critical Error'
)
smtp_handler.setLevel(logging.CRITICAL)
self.logger.addHandler(smtp_handler)
```

---

## 🛠️ صيانة Logs

### تنظيف Logs القديمة

```python
# cleanup_logs.py
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_logs(days_to_keep=30):
    """حذف logs أقدم من عدد معين من الأيام"""
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    logs_dir = Path("logs")
    
    for log_type in ["prompts", "responses", "errors", "analytics"]:
        type_dir = logs_dir / log_type
        if not type_dir.exists():
            continue
        
        for log_file in type_dir.iterdir():
            if log_file.is_file():
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    log_file.unlink()
                    print(f"Deleted: {log_file}")

if __name__ == "__main__":
    cleanup_old_logs(days_to_keep=30)
```

### أرشفة Logs

```python
# archive_logs.py
import shutil
from pathlib import Path
from datetime import datetime

def archive_logs():
    """أرشفة logs الشهر الماضي"""
    
    last_month = datetime.now().replace(day=1) - timedelta(days=1)
    archive_name = f"logs_archive_{last_month.strftime('%Y%m')}"
    
    # إنشاء أرشيف مضغوط
    shutil.make_archive(
        archive_name,
        'zip',
        'logs'
    )
    
    print(f"Archive created: {archive_name}.zip")

if __name__ == "__main__":
    archive_logs()
```

---

## 📈 مثال على التقرير اليومي

```python
# daily_report.py
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def generate_daily_report(date_str=None):
    """إنشاء تقرير يومي"""
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    analytics_file = Path(f"logs/analytics/analytics_{date_str}.jsonl")
    
    if not analytics_file.exists():
        print(f"No analytics file found for {date_str}")
        return
    
    # قراءة البيانات
    analyses = []
    with open(analytics_file, 'r', encoding='utf-8') as f:
        analyses = [json.loads(line) for line in f]
    
    # حساب الإحصائيات
    total = len(analyses)
    successful = sum(1 for a in analyses if a['success'])
    failed = total - successful
    
    if successful > 0:
        avg_compliance = sum(a['compliance_ratio'] for a in analyses if a['success']) / successful
        avg_duration = sum(a['duration_seconds'] for a in analyses if a['success']) / successful
    else:
        avg_compliance = 0
        avg_duration = 0
    
    # تجميع حسب نوع السياسة
    by_policy = defaultdict(int)
    for a in analyses:
        by_policy[a['policy_type']] += 1
    
    # طباعة التقرير
    print("=" * 80)
    print(f"📊 Daily Report - {date_str}")
    print("=" * 80)
    print(f"Total Analyses: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"\nAverage Compliance: {avg_compliance:.1f}%")
    print(f"Average Duration: {avg_duration:.2f} seconds")
    print(f"\nAnalyses by Policy Type:")
    for policy_type, count in by_policy.items():
        print(f"  - {policy_type}: {count}")
    print("=" * 80)

if __name__ == "__main__":
    generate_daily_report()
```

---

## ✅ Best Practices

1. **لا تعطل Logging في Production** - Logs مهمة لتتبع المشاكل
2. **راقب حجم Logs** - نظف أو أرشف Logs القديمة بانتظام
3. **استخدم المستويات المناسبة**:
   - DEBUG: تفاصيل التطوير فقط
   - INFO: عمليات عادية
   - WARNING: أمور غير متوقعة لكن غير حرجة
   - ERROR: أخطاء تحتاج انتباه
   - CRITICAL: أخطاء حرجة تحتاج تدخل فوري
4. **حافظ على خصوصية البيانات** - لا تسجل بيانات حساسة للعملاء
5. **استخدم Structured Logging** - JSON للبيانات المعقدة

---

## 🔒 الأمان والخصوصية

⚠️ **تحذير مهم:**

- لا تسجل بيانات شخصية حساسة (أرقام بطاقات، كلمات مرور)
- تأكد من حماية مجلد `logs/` من الوصول العام
- استخدم `.gitignore` لعدم رفع Logs على Git
- اعتبر تشفير Logs الحساسة

```gitignore
# .gitignore
logs/
*.log
```

---

**تم! نظام Logging جاهز للاستخدام 🎉**
