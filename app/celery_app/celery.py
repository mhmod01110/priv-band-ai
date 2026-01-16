"""
Celery Application Configuration with Optimized Concurrency
"""

from celery import Celery
from app.config import get_settings
from app.celery_app import signals

settings = get_settings()

celery_app = Celery(
    'legal_policy_analyzer',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.celery_app.tasks']
)

# 🔥 إعدادات محسّنة للـ concurrency
celery_app.conf.update(
    # Task execution settings
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_acks_late=settings.celery_task_acks_late,
    
    # 🚀 Prefetch: زودناه لتحسين throughput
    worker_prefetch_multiplier=4,  # كان 1، دلوقتي 4
    
    # 🚀 Concurrency: السماح بتنفيذ tasks متعددة
    worker_concurrency=10,  # default للـ gevent pool
    
    # 🚀 Performance: تقليل overhead
    worker_disable_rate_limits=True,
    task_compression='gzip',  # ضغط البيانات
    result_compression='gzip',
    
    # Result settings
    result_expires=settings.celery_result_expires,
    result_persistent=True,
    
    # MongoDB backend settings
    mongodb_backend_settings={
        'database': settings.mongodb_database,
        'taskmeta_collection': 'celery_taskmeta',
        'groupmeta_collection': 'celery_groupmeta',
    },
    
    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Timezone
    timezone='Asia/Riyadh',
    enable_utc=True,
    
    # Retry settings
    task_default_retry_delay=settings.celery_task_default_retry_delay,
    task_max_retries=settings.celery_task_max_retries,
    
    # RabbitMQ settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,  # زودنا الـ pool size
    
    # 🚀 Task routing optimization
    task_routes={
        'app.celery_app.tasks.*': {'queue': 'celery'},
    },
    
    # Worker settings
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat schedule
    beat_schedule={
        'cleanup-old-results': {
            'task': 'app.celery_app.tasks.cleanup_old_results',
            'schedule': 3600.0,
        },
    },
)

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery"""
    print(f'Request: {self.request!r}')