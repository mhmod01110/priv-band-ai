# Legal Policy Analyzer 📋⚖️

محلل احترافي لسياسات المتاجر الإلكترونية للتحقق من الامتثال القانوني للأنظمة السعودية.

يدعم **OpenAI GPT-4** و **Google Gemini** 🤖

---

## 🌟 المميزات

✅ تحليل شامل للامتثال القانوني  
✅ دعم OpenAI و Gemini  
✅ إعادة كتابة السياسات تلقائياً  
✅ تقارير تفصيلية باللغة العربية  
✅ حماية كاملة من التكرار والإساءة  
✅ Idempotency للطلبات  

---

## 📦 التثبيت

### 1. استنساخ المشروع

```bash
git clone https://github.com/your-repo/legal-policy-analyzer.git
cd legal-policy-analyzer
```

### 2. إنشاء بيئة افتراضية

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# أو
venv\Scripts\activate  # Windows
```

### 3. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 4. إعداد ملف البيئة

```bash
cp .env.example .env
```

ثم افتح `.env` وأضف مفاتيح API:

```bash
# اختر المزود
AI_PROVIDER=openai  # أو gemini

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Gemini
GEMINI_API_KEY=your-gemini-key-here
```

---

## 🚀 التشغيل

### تشغيل الخادم

```bash
python -m uvicorn app.main:app --reload --port 8000
```

سيعمل:
- **API**: http://localhost:8000
- **HTML Interface**: http://localhost:5000
- **API Docs**: http://localhost:8000/docs

---

## 🔧 التبديل بين OpenAI و Gemini

### طريقة 1: من ملف `.env`

```bash
# في ملف .env
AI_PROVIDER=gemini  # أو openai
```

### طريقة 2: برمجياً في الكود

```python
from app.services.analyzer_service import AnalyzerService

# استخدام OpenAI
analyzer = AnalyzerService(provider="openai")

# استخدام Gemini
analyzer = AnalyzerService(provider="gemini")
```

### طريقة 3: عبر API

```bash
# إرسال طلب مع تحديد المزود
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_name": "متجر الأزياء",
    "shop_specialization": "ملابس نسائية",
    "policy_type": "سياسات الاسترجاع و الاستبدال",
    "policy_text": "نص السياسة هنا...",
    "provider": "gemini"
  }'
```

---

## 📖 أمثلة الاستخدام

### مثال 1: تحليل سياسة (Python)

```python
import asyncio
from app.services.analyzer_service import AnalyzerService
from app.models import PolicyAnalysisRequest, PolicyType

async def analyze_example():
    # استخدام Gemini
    analyzer = AnalyzerService(provider="gemini")
    
    request = PolicyAnalysisRequest(
        shop_name="متجر الإلكترونيات",
        shop_specialization="أجهزة كهربائية",
        policy_type=PolicyType.RETURN_EXCHANGE,
        policy_text="يمكن إرجاع المنتج خلال 7 أيام..."
    )
    
    result = await analyzer.analyze_policy(request)
    
    if result.success:
        print(f"نسبة الامتثال: {result.compliance_report.overall_compliance_ratio}%")
        print(f"عدد المشاكل: {len(result.compliance_report.critical_issues)}")
    else:
        print(f"خطأ: {result.message}")

asyncio.run(analyze_example())
```

### مثال 2: استخدام API

```bash
# تحليل سياسة
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique-key-123" \
  -d '{
    "shop_name": "متجر الأزياء",
    "shop_specialization": "ملابس نسائية",
    "policy_type": "سياسات الاسترجاع و الاستبدال",
    "policy_text": "البضاعة المباعة لا ترد ولا تستبدل"
  }'
```

---

## 🔐 الأمان والحماية

### Rate Limiting
- **20 طلب** في الدقيقة لكل IP
- حظر لمدة **15 دقيقة** عند التجاوز

### Idempotency
- منع معالجة نفس الطلب مرتين
- TTL: 24 ساعة

### Input Validation
- فحص المحتوى المشبوه
- حد أقصى 50,000 حرف
- حد أدنى 50 حرف

### Circuit Breaker
- يوقف الطلبات بعد 5 أخطاء متتالية
- فترة الاسترداد: 2 دقيقة

---

## 🧪 الاختبارات

```bash
# تشغيل جميع الاختبارات
pytest tests/

# اختبار محدد
pytest tests/test_analyzer_service.py -v
```

---

## 📊 المقارنة بين OpenAI و Gemini

| الميزة | OpenAI GPT-4 | Google Gemini |
|--------|-------------|---------------|
| السرعة | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| الدقة | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| التكلفة | $$$ | $$ |
| العربية | ممتاز | جيد جداً |
| JSON | ممتاز | جيد |

---

## 🗂️ هيكل المشروع

```
legal-policy-analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI الرئيسي
│   ├── config.py                  # الإعدادات
│   ├── models.py                  # النماذج
│   ├── logger.py                  # نظام السجلات
│   ├── safeguards.py              # الحماية
│   ├── middleware.py              # Middlewares
│   ├── services/
│   │   ├── __init__.py
│   │   ├── openai_service.py     # خدمة OpenAI
│   │   ├── gemini_service.py     # خدمة Gemini ✨
│   │   ├── analyzer_service.py   # خدمة التحليل
│   │   └── idempotency_service.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── system_prompt.py
│   │   ├── policy_matcher.py
│   │   ├── compliance_analyzer.py
│   │   ├── compliance_rules.py
│   │   └── policy_generator.py
│   └── utils/
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   └── js/
├── tests/
├── logs/
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🤝 المساهمة

نرحب بالمساهمات! الرجاء:

1. Fork المشروع
2. إنشاء branch للميزة (`git checkout -b feature/AmazingFeature`)
3. Commit التغييرات (`git commit -m 'Add AmazingFeature'`)
4. Push للـ branch (`git push origin feature/AmazingFeature`)
5. فتح Pull Request

---

## 📄 الترخيص

هذا المشروع مرخص تحت [MIT License](LICENSE).

---

## 📞 التواصل

- **البريد الإلكتروني**: your-email@example.com
- **الموقع**: https://your-website.com

---

## 🙏 شكر وتقدير

- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenAI](https://openai.com/)
- [Google Gemini](https://deepmind.google/technologies/gemini/)
- [Pydantic](https://docs.pydantic.dev/)

---

**صُنع بـ ❤️ في السعودية 🇸🇦**
