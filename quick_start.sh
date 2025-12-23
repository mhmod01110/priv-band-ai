###############################################################
# Legal Policy Analyzer - دليل البدء السريع
###############################################################

# 1. إنشاء مجلد المشروع وهيكله
mkdir legal-policy-analyzer
cd legal-policy-analyzer

# إنشاء الهيكل الكامل
mkdir -p app/prompts app/services app/utils static/css static/js templates tests

# 2. إنشاء البيئة الافتراضية
python -m venv venv

# تفعيل البيئة
# في Windows:
venv\Scripts\activate
# في Linux/Mac:
# source venv/bin/activate

# 3. إنشاء ملف المتطلبات
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.0.0
python-dotenv==1.0.0
openai==1.3.0
python-multipart==0.0.6
jinja2==3.1.2
aiofiles==23.2.1
pytest==7.4.3
httpx==0.25.1
EOF

# 4. تثبيت المكتبات
pip install -r requirements.txt

# 5. إنشاء ملف البيئة
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview
EOF

# تنبيه: قم بتعديل مفتاح OpenAI API في ملف .env

# 6. إنشاء ملف .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
venv/
.env
.pytest_cache/
.DS_Store
EOF

# 7. بعد إنشاء جميع الملفات (models.py, main.py, إلخ)
# قم بتشغيل الخادم:

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 8. افتح المتصفح
# http://localhost:8000

# 9. لتشغيل الاختبارات
pytest tests/ -v

# 10. لبناء الحزمة
python setup.py sdist bdist_wheel

###############################################################
# اختبار API من Command Line
###############################################################

# اختبار فحص الصحة
curl http://localhost:8000/health

# اختبار التحليل
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_name": "متجر التجربة",
    "shop_specialization": "إلكترونيات",
    "policy_type": "سياسات الاسترجاع و الاستبدال",
    "policy_text": "يحق للعميل إرجاع المنتج خلال 7 أيام من تاريخ الاستلام دون إبداء الأسباب. يجب أن يكون المنتج في حالته الأصلية مع الفاتورة الأصلية."
  }'

###############################################################
# قائمة الملفات المطلوب إنشاؤها
###############################################################

# الملفات الرئيسية:
# - app/__init__.py
# - app/main.py
# - app/models.py
# - app/config.py
# - app/prompts/__init__.py
# - app/prompts/policy_matcher.py
# - app/prompts/compliance_analyzer.py
# - app/prompts/compliance_rules.py
# - app/services/__init__.py
# - app/services/openai_service.py
# - app/services/analyzer_service.py
# - app/utils/__init__.py
# - templates/index.html
# - tests/__init__.py
# - tests/test_api.py
# - requirements.txt
# - setup.py
# - pyproject.toml
# - README.md
# - .env
# - .gitignore

###############################################################
# ملاحظات مهمة
###############################################################

# 1. تأكد من إضافة مفتاح OpenAI API الصحيح في .env
# 2. النظام يحتاج اتصال بالإنترنت للاتصال بـ OpenAI
# 3. التحليل يستغرق 10-30 ثانية حسب طول النص
# 4. استخدام GPT-4 له تكلفة، راقب استهلاكك
# 5. النظام مصمم للنصوص العربية فقط

###############################################################
# للدعم والمساعدة
###############################################################

# إذا واجهت مشاكل:
# 1. تحقق من تثبيت جميع المكتبات
# 2. تحقق من مفتاح OpenAI API
# 3. تحقق من سجلات الأخطاء في Console
# 4. راجع ملف README.md للتفاصيل

# انتهى - بالتوفيق! 🚀
