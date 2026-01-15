#!/usr/bin/env python
"""
Celery Worker Entrypoint with Proper Async Concurrency
Run with: python app/celery_worker.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app.celery import celery_app
from app.logger import app_logger

if __name__ == '__main__':
    app_logger.info("🚀 Starting Celery Worker with Gevent Pool...")
    
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        
        # 🔥 الحل الأساسي: استخدام gevent pool للـ async tasks
        '--pool=gevent',  # ده الأهم - بدل prefork
        '--concurrency=50',  # عدد greenlets (ممكن تزوده لـ 100-200)
        
        # إعدادات إضافية
        '--max-tasks-per-child=1000',
        '--time-limit=600',
        '--soft-time-limit=540',
        
        # تحسين الأداء
        '--prefetch-multiplier=4',  # زودناه من 1 لـ 4
        '--without-gossip',  # تقليل overhead
        '--without-mingle',  # تقليل startup time
        '--without-heartbeat',  # optional - لو مش محتاج heartbeat
    ])