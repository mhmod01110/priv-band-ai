#!/usr/bin/env python
from gevent import monkey
monkey.patch_all()  # must be first

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app.celery import celery_app
from app.logger import app_logger

if __name__ == '__main__':
    app_logger.info("🚀 Starting Celery Worker with Gevent Pool...")
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--pool=gevent",
        "--concurrency=10",
        "-E",
    ])
