# app/__init__.py
"""
Legal Policy Analyzer
محلل الامتثال القانوني للمتاجر الإلكترونية
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__description__ = "تحليل سياسات المتاجر الإلكترونية للامتثال القانوني"

# إنشاء مجلد logs عند استيراد الحزمة
from pathlib import Path

logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)
(logs_dir / "prompts").mkdir(exist_ok=True)
(logs_dir / "responses").mkdir(exist_ok=True)
(logs_dir / "errors").mkdir(exist_ok=True)
(logs_dir / "analytics").mkdir(exist_ok=True)