"""
Celery Application Configuration with RabbitMQ
"""
from celery import Celery
from app.config import get_settings
from app.celery_app import signals

settings = get_settings()

# Create Celery instance with RabbitMQ broker and MongoDB result backend
celery_app = Celery(
    'legal_policy_analyzer',
    broker=settings.celery_broker_url,  # RabbitMQ: amqp://...
    backend=settings.celery_result_backend,  # MongoDB: mongodb://...
    include=['app.celery_app.tasks']  # Auto-discover tasks
)

# Celery Configuration
celery_app.conf.update(
    # Task execution settings
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_acks_late=settings.celery_task_acks_late,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    
    # Result settings
    result_expires=settings.celery_result_expires,
    result_persistent=True,
    
    # MongoDB result backend specific settings
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
    
    # RabbitMQ specific settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Task result settings
    result_backend_transport_options={
        'master_name': 'mymaster',
    },
    
    # Worker settings
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat schedule (for periodic tasks)
    beat_schedule={
        'cleanup-old-results': {
            'task': 'app.celery_app.tasks.cleanup_old_results',
            'schedule': 3600.0,  # Every hour
        },
    },
)

# Celery events
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery"""
    print(f'Request: {self.request!r}')
    
