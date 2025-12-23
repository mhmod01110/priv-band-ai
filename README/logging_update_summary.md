# 🎉 تحديث نظام Logging - ملخص التغييرات

## ✅ الملفات الجديدة المضافة

### 1. `app/logger.py` (ملف جديد)
نظام Logging شامل يتضمن:
- **StructuredLogger Class**: Logger متقدم مع ميزات خاصة
- **ColoredFormatter**: تنسيق ملون للـ Console
- **4 أنواع من Handlers**:
  - Console Handler (ملون)
  - General Log File
  - Error Log File
  - Rotating handlers للأداء

### 2. `LOGGING_GUIDE.md` (دليل شامل)
دليل كامل يشرح:
- كيفية استخدام Logger
- هيكل Logs
- أمثلة عملية
- تحليل Logs
- Best practices

### 3. `scripts.py` (سكريبتات مساعدة)
أدوات لإدارة Logs:
- `cleanup_old_logs()` - حذف logs قديمة
- `archive_logs()` - أرشفة logs
- `generate_daily_report()` - تقارير يومية
- `analyze_errors()` - تحليل الأخطاء

---

## 🔄 الملفات المُحدثة

### 1. `app/services/openai_service.py`
**التغييرات:**
```python
# إضافة
from app.logger import app_logger
import time
import traceback

class OpenAIService:
    def __init__(self):
        # ... existing code
        self.logger = app_logger
    
    async def analyze_with_prompt(...):
        # تسجيل وقت البدء
        start_time = time.time()
        
        # تسجيل معلومات API call
        self.logger.info(f"OpenAI API call - Duration: {duration}")
        
        # تسجيل الأخطاء مع traceback
        except Exception as e:
            self.logger.log_error(...)
    
    async def check_policy_match(...):
        # تسجيل Prompt
        self.logger.log_prompt(stage="stage1_match", ...)
        
        # تسجيل Response
        self.logger.log_response(stage="stage1_match", ...)
    
    async def analyze_compliance(...):
        # تسجيل Prompt
        self.logger.log_prompt(stage="stage2_analyze", ...)
        
        # تسجيل Response
        self.logger.log_response(stage="stage2_analyze", ...)
```

### 2. `app/services/analyzer_service.py`
**التغييرات:**
```python
# إضافة
from app.logger import app_logger
import time
import traceback

class AnalyzerService:
    def __init__(self):
        self.logger = app_logger
    
    async def analyze_policy(...):
        # تسجيل بداية التحليل
        self.logger.info("Starting new analysis")
        start_time = time.time()
        
        # تسجيل Stage 1
        self.logger.info("Stage 1: Policy Match Check")
        
        # تسجيل Stage 2
        self.logger.info("Stage 2: Compliance Analysis")
        
        # تسجيل ملخص التحليل
        self.logger.log_analysis_summary(
            shop_name=...,
            compliance_ratio=...,
            duration=...,
            success=True
        )
        
        # تسجيل الأخطاء
        except Exception as e:
            self.logger.log_error(...)
```

### 3. `app/main.py`
**التغييرات:**
```python
# إضافة
from app.logger import app_logger

@app.on_event("startup")
async def startup_event():
    app_logger.info("Application starting...")

@app.on_event("shutdown")
async def shutdown_event():
    app_logger.info("Application shutting down...")

@app.post("/api/analyze")
async def analyze_policy(...):
    app_logger.info(f"New analysis request - Shop: {request.shop_name}")
    
    if result.success:
        app_logger.info("Analysis completed successfully")
    else:
        app_logger.warning("Analysis completed with issues")
```

### 4. `app/__init__.py`
**التغييرات:**
```python
# إضافة إنشاء تلقائي لمجلد logs
from pathlib import Path

logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)
(logs_dir / "prompts").mkdir(exist_ok=True)
(logs_dir / "responses").mkdir(exist_ok=True)
(logs_dir / "errors").mkdir(exist_ok=True)
(logs_dir / "analytics").mkdir(exist_ok=True)
```

### 5. `.gitignore`
**إضافة:**
```
# Logs
logs/
*.log

# Archives
*.zip
*.tar.gz
```

### 6. `README.md`
**إضافة قسم:**
- نظام Logging وميزاته
- سكريبتات إدارة Logs
- رابط لـ LOGGING_GUIDE.md

---

## 📊 ما يتم تسجيله

### 1. Prompts (`logs/prompts/`)
كل prompt مُرسل إلى OpenAI:
```
20241214_153045_stage1_match_متجر_الأزياء.txt
20241214_153050_stage2_analyze_متجر_الأزياء.txt
```

محتوى كل ملف:
- Metadata (timestamp, stage, shop_name, policy_type)
- النص الكامل للـ Prompt

### 2. Responses (`logs/responses/`)
كل استجابة من OpenAI:
```
20241214_153045_stage1_match_متجر_الأزياء.json
20241214_153050_stage2_analyze_متجر_الأزياء.json
```

محتوى كل ملف:
- Metadata
- الاستجابة الكاملة بصيغة JSON

### 3. Analytics (`logs/analytics/`)
إحصائيات يومية:
```
analytics_20241214.jsonl
```

كل سطر = تحليل واحد:
```json
{"timestamp": "...", "shop_name": "...", "compliance_ratio": 78.5, "duration": 25.3, "success": true}
```

### 4. Errors (`logs/errors/`)
جميع الأخطاء:
```
errors_20241214.log       # log file يومي
error_20241214_153100.json  # ملف JSON لكل خطأ
```

### 5. General Log (`logs/app.log`)
Log عام لجميع العمليات

---

## 🎨 مثال على Console Output

```
2024-12-14 15:30:45 - legal_policy_analyzer - INFO - 🚀 Legal Policy Analyzer API Starting...
2024-12-14 15:30:45 - legal_policy_analyzer - INFO - 📝 Version: 1.0.0
2024-12-14 15:30:45 - legal_policy_analyzer - INFO - 🤖 OpenAI Model: gpt-4-turbo-preview
2024-12-14 15:30:45 - legal_policy_analyzer - INFO - ✅ Application started successfully
2024-12-14 15:31:00 - legal_policy_analyzer - INFO - 📨 New analysis request received - Shop: متجر الأزياء
2024-12-14 15:31:00 - legal_policy_analyzer - INFO - ================================================================================
2024-12-14 15:31:00 - legal_policy_analyzer - INFO - 🚀 Starting new analysis
2024-12-14 15:31:00 - legal_policy_analyzer - INFO - Shop: متجر الأزياء
2024-12-14 15:31:00 - legal_policy_analyzer - INFO - ▶ Stage 1: Policy Match Check
2024-12-14 15:31:01 - legal_policy_analyzer - INFO - 📝 Prompt logged: stage1_match - متجر الأزياء - 2456 chars
2024-12-14 15:31:05 - legal_policy_analyzer - INFO - OpenAI API call successful - Duration: 4.23s - Tokens: 3241
2024-12-14 15:31:05 - legal_policy_analyzer - INFO - 📥 Response logged: stage1_match - متجر الأزياء
2024-12-14 15:31:05 - legal_policy_analyzer - INFO - ✅ Policy matched - Confidence: 95.5%
2024-12-14 15:31:05 - legal_policy_analyzer - INFO - ▶ Stage 2: Compliance Analysis
2024-12-14 15:31:06 - legal_policy_analyzer - INFO - 📝 Prompt logged: stage2_analyze - متجر الأزياء - 5832 chars
2024-12-14 15:31:25 - legal_policy_analyzer - INFO - OpenAI API call successful - Duration: 18.87s - Tokens: 7845
2024-12-14 15:31:25 - legal_policy_analyzer - INFO - 📥 Response logged: stage2_analyze - متجر الأزياء
2024-12-14 15:31:25 - legal_policy_analyzer - INFO - ✅ Analysis completed successfully - Compliance: 78.5% - Duration: 25.32s
2024-12-14 15:31:25 - legal_policy_analyzer - INFO - 📊 Analysis completed: متجر الأزياء - Compliance: 78.5% - Duration: 25.32s
2024-12-14 15:31:25 - legal_policy_analyzer - INFO - ✅ Analysis request completed successfully - Shop: متجر الأزياء
```

---

## 🛠️ استخدام السكريبتات

### تنظيف Logs القديمة
```bash
# فحص تجريبي (عرض فقط)
python scripts.py cleanup 30 --dry-run

# تنفيذ فعلي
python scripts.py cleanup 30
```

### أرشفة Logs
```bash
# أرشفة شهر معين
python scripts.py archive 202412

# أرشفة الشهر الماضي
python scripts.py archive
```

### تقرير يومي
```bash
# تقرير لتاريخ معين
python scripts.py daily-report 20241214

# تقرير لليوم الحالي
python scripts.py daily-report
```

### تحليل الأخطاء
```bash
# آخر 7 أيام
python scripts.py analyze-errors 7

# آخر 30 يوم
python scripts.py analyze-errors 30
```

---

## 📈 فوائد نظام Logging

### 1. التتبع والمراقبة
- معرفة ما يحدث داخل النظام بالضبط
- تتبع جميع Prompts والاستجابات
- مراقبة الأداء (المدة الزمنية، عدد Tokens)

### 2. اكتشاف المشاكل
- تسجيل تفصيلي للأخطاء
- Traceback كامل لكل خطأ
- تحليل أنماط الأخطاء

### 3. التحسين المستمر
- تحليل Prompts الناجحة
- تحديد نقاط الضعف
- قياس جودة النتائج

### 4. الإحصائيات
- عدد التحليلات اليومية
- متوسط نسبة الامتثال
- توزيع أنواع السياسات
- أكثر المتاجر تحليلاً

### 5. Debugging
- إعادة تشغيل نفس Prompt بالضبط
- مقارنة نتائج مختلفة
- فهم سلوك النموذج

---

## ⚙️ التخصيص

### تغيير مستوى Logging
في `app/logger.py`:
```python
self.logger.setLevel(logging.DEBUG)   # كل شيء
self.logger.setLevel(logging.INFO)    # INFO وما فوق
self.logger.setLevel(logging.WARNING) # تحذيرات وأخطاء فقط
```

### إضافة Handler جديد
مثال: إرسال أخطاء حرجة عبر البريد
```python
import logging.handlers

smtp_handler = logging.handlers.SMTPHandler(
    mailhost=('smtp.gmail.com', 587),
    fromaddr='app@example.com',
    toaddrs=['admin@example.com'],
    subject='Critical Error - Legal Analyzer'
)
smtp_handler.setLevel(logging.CRITICAL)
self.logger.addHandler(smtp_handler)
```

### تعطيل Logging مؤقتاً
```python
import logging

# تعطيل الـ prompts/responses logging
logging.getLogger('legal_policy_analyzer').setLevel(logging.WARNING)
```

---

## 🔒 الأمان

### ⚠️ تحذيرات مهمة:

1. **لا ترفع logs على Git**
   - تأكد من إضافة `logs/` في `.gitignore`

2. **احذر من البيانات الحساسة**
   - Logs قد تحتوي على معلومات حساسة
   - لا تشارك logs علناً

3. **حماية مجلد logs**
   - تأكد من صلاحيات الوصول المناسبة
   - استخدم HTTPS في Production

4. **تنظيف دوري**
   - احذف logs قديمة بانتظام
   - أو أرشفها بشكل آمن

---

## ✅ قائمة التحقق

- [x] تم إضافة `app/logger.py`
- [x] تم تحديث `openai_service.py`
- [x] تم تحديث `analyzer_service.py`
- [x] تم تحديث `main.py`
- [x] تم تحديث `__init__.py`
- [x] تم إنشاء `LOGGING_GUIDE.md`
- [x] تم إنشاء `scripts.py`
- [x] تم تحديث `.gitignore`
- [x] تم تحديث `README.md`
- [x] سيتم إنشاء مجلد `logs/` تلقائياً عند التشغيل

---

## 🚀 البدء

```bash
# 1. تثبيت (لا توجد مكتبات إضافية مطلوبة)
pip install -r requirements.txt

# 2. تشغيل التطبيق
uvicorn app.main:app --reload

# 3. مجلد logs سيتم إنشاؤه تلقائياً
# 4. ابدأ في استخدام النظام
# 5. راقب Console للـ logs الملونة
# 6. افحص مجلد logs/ للتفاصيل
```

---

**تم بنجاح! نظام Logging جاهز ومتكامل 🎉**

جميع Prompts والاستجابات والأخطاء سيتم تسجيلها تلقائياً!
