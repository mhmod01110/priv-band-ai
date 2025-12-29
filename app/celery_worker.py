#!/usr/bin/env python
"""
Celery Worker Entrypoint
Run with: celery -A celery_worker worker --loglevel=info
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app.celery import celery_app
from app.logger import app_logger

if __name__ == '__main__':
    app_logger.info("🚀 Starting Celery Worker...")
    
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=10',  # Number of concurrent workers
        '--max-tasks-per-child=1000',  # Restart worker after N tasks (prevents memory leaks)
        '--time-limit=600',  # Hard time limit (10 minutes)
        '--soft-time-limit=540',  # Soft time limit (9 minutes)
    ])