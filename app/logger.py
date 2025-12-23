import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import sys

class ColoredFormatter(logging.Formatter):
    """Formatter ملون للـ Console"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class StructuredLogger:
    """
    Logger متقدم لتسجيل Prompts والاستجابات
    """
    
    def __init__(self, name: str = "legal_policy_analyzer"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # إنشاء مجلد logs
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # إنشاء مجلدات فرعية
        (self.logs_dir / "prompts").mkdir(exist_ok=True)
        (self.logs_dir / "responses").mkdir(exist_ok=True)
        (self.logs_dir / "errors").mkdir(exist_ok=True)
        (self.logs_dir / "analytics").mkdir(exist_ok=True)
        
        # إعداد handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """إعداد جميع handlers"""
        
        # تنظيف handlers السابقة
        self.logger.handlers.clear()
        
        # 1. Console Handler (ملون)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 2. General Log File
        general_handler = logging.FileHandler(
            self.logs_dir / "app.log",
            encoding='utf-8'
        )
        general_handler.setLevel(logging.DEBUG)
        general_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        general_handler.setFormatter(general_formatter)
        self.logger.addHandler(general_handler)
        
        # 3. Error Log File
        error_handler = logging.FileHandler(
            self.logs_dir / "errors" / f"errors_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(general_formatter)
        self.logger.addHandler(error_handler)
    
    def log_prompt(
        self,
        stage: str,
        shop_name: str,
        policy_type: str,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        تسجيل Prompt مُرسل إلى OpenAI
        
        Args:
            stage: مرحلة التحليل (stage1_match, stage2_analyze)
            shop_name: اسم المتجر
            policy_type: نوع السياسة
            prompt: نص الـ Prompt
            metadata: بيانات إضافية
        """
        timestamp = datetime.now()
        filename = (
            f"{timestamp.strftime('%Y%m%d_%H%M%S')}_"
            f"{stage}_{shop_name[:20].replace(' ', '_')}.txt"
        )
        
        prompt_data = {
            "timestamp": timestamp.isoformat(),
            "stage": stage,
            "shop_name": shop_name,
            "policy_type": policy_type,
            "prompt_length": len(prompt),
            "metadata": metadata or {}
        }
        
        # حفظ الـ Prompt في ملف منفصل
        prompt_file = self.logs_dir / "prompts" / filename
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PROMPT METADATA\n")
            f.write("=" * 80 + "\n")
            f.write(json.dumps(prompt_data, ensure_ascii=False, indent=2))
            f.write("\n\n")
            f.write("=" * 80 + "\n")
            f.write("PROMPT CONTENT\n")
            f.write("=" * 80 + "\n")
            f.write(prompt)
        
        self.logger.info(
            f"📝 Prompt logged: {stage} - {shop_name} - {len(prompt)} chars - {filename}"
        )
    
    def log_response(
        self,
        stage: str,
        shop_name: str,
        policy_type: str,
        response: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        تسجيل استجابة OpenAI
        
        Args:
            stage: مرحلة التحليل
            shop_name: اسم المتجر
            policy_type: نوع السياسة
            response: الاستجابة من OpenAI
            metadata: بيانات إضافية
        """
        timestamp = datetime.now()
        filename = (
            f"{timestamp.strftime('%Y%m%d_%H%M%S')}_"
            f"{stage}_{shop_name[:20].replace(' ', '_')}.json"
        )
        
        response_data = {
            "timestamp": timestamp.isoformat(),
            "stage": stage,
            "shop_name": shop_name,
            "policy_type": policy_type,
            "response": response,
            "metadata": metadata or {}
        }
        
        # حفظ الاستجابة في ملف JSON
        response_file = self.logs_dir / "responses" / filename
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(
            f"📥 Response logged: {stage} - {shop_name} - {filename}"
        )
    
    def log_analysis_summary(
        self,
        shop_name: str,
        policy_type: str,
        compliance_ratio: float,
        duration: float,
        success: bool
    ):
        """
        تسجيل ملخص التحليل للإحصائيات
        """
        timestamp = datetime.now()
        
        summary = {
            "timestamp": timestamp.isoformat(),
            "date": timestamp.strftime('%Y-%m-%d'),
            "time": timestamp.strftime('%H:%M:%S'),
            "shop_name": shop_name,
            "policy_type": policy_type,
            "compliance_ratio": compliance_ratio,
            "duration_seconds": round(duration, 2),
            "success": success
        }
        
        # حفظ في ملف يومي للإحصائيات
        analytics_file = self.logs_dir / "analytics" / f"analytics_{timestamp.strftime('%Y%m%d')}.jsonl"
        with open(analytics_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        
        self.logger.info(
            f"📊 Analysis completed: {shop_name} - "
            f"Compliance: {compliance_ratio}% - Duration: {duration:.2f}s"
        )
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        shop_name: Optional[str] = None,
        traceback_info: Optional[str] = None
    ):
        """
        تسجيل الأخطاء بشكل مفصل
        """
        timestamp = datetime.now()
        
        error_data = {
            "timestamp": timestamp.isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "shop_name": shop_name,
            "traceback": traceback_info
        }
        
        # حفظ الخطأ
        error_file = self.logs_dir / "errors" / f"error_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
        
        self.logger.error(
            f"❌ Error: {error_type} - {error_message}" +
            (f" - Shop: {shop_name}" if shop_name else "")
        )
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(f"🔍 {message}")
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(f"ℹ️  {message}")
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(f"⚠️  {message}")
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(f"❌ {message}")
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(f"🚨 {message}")

# إنشاء logger عام للتطبيق
app_logger = StructuredLogger("legal_policy_analyzer")
