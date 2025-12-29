#!/usr/bin/env python
"""
Celery Beat Scheduler Entrypoint
Run with: celery -A celery_beat beat --loglevel=info
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app.celery import celery_app
from app.logger import app_logger

if __name__ == '__main__':
    app_logger.info("⏰ Starting Celery Beat Scheduler...")
    
    celery_app.Beat().run()