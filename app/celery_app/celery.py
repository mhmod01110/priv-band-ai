from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    'legal_policy_analyzer',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.celery_app.tasks']
)

celery_app.conf.update(
    # Task execution settings
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_acks_late=settings.celery_task_acks_late,
    
    # 🚀 Concurrency & Prefetch
    worker_concurrency=settings.celery_worker_concurrency,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    
    # 🚀 Performance & Compression
    worker_disable_rate_limits=settings.celery_worker_disable_rate_limits,
    task_compression=settings.celery_task_compression,
    result_compression=settings.celery_result_compression,
    
    # Result settings
    result_expires=settings.celery_result_expires,
    result_persistent=True,
    
    # MongoDB backend settings
    mongodb_backend_settings={
        'database': settings.mongodb_database,
        'taskmeta_collection': 'celery_taskmeta',
    },
    
    # Broker & Connection Pool
    broker_pool_limit=settings.celery_broker_pool_limit,
    broker_connection_retry=settings.celery_broker_connection_retry,
    broker_connection_max_retries=settings.celery_broker_connection_max_retries,
    broker_connection_retry_on_startup=True,
    
    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Retry settings
    task_default_retry_delay=settings.celery_task_default_retry_delay,
    task_max_retries=settings.celery_task_max_retries,
    
    timezone='Asia/Riyadh',
    enable_utc=True,
)