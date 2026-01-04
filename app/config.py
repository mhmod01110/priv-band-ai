from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # ============================================
    # AI Provider Selection
    # ============================================
    ai_provider: str = "openai"
    
    # ============================================
    # OpenAI Configuration
    # ============================================
    openai_api_key: str = ""
    openai_light_model: str = "gpt-4o-mini"
    openai_light_temperature: float = 0.2
    openai_light_max_tokens: int = 2000
    openai_heavy_model: str = "gpt-4o"
    openai_heavy_temperature: float = 0.3
    openai_heavy_max_tokens: int = 16000
    
    # ============================================
    # Gemini Configuration
    # ============================================
    gemini_api_key: str = ""
    gemini_light_model: str = "gemini-1.5-flash"
    gemini_light_temperature: float = 0.2
    gemini_light_max_tokens: int = 2000
    gemini_heavy_model: str = "gemini-2.0-flash-exp"
    gemini_heavy_temperature: float = 0.3
    gemini_heavy_max_tokens: int = 16000
    
    # ============================================
    # MongoDB Configuration
    # ============================================
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "legal_policy_analyzer"
    mongodb_username: str = ""
    mongodb_password: str = ""
    mongodb_auth_source: str = "admin"
    mongodb_min_pool_size: int = 10
    mongodb_max_pool_size: int = 100
    mongodb_timeout: int = 5000
    
    # ============================================
    # RabbitMQ Configuration (Replaces Redis for Celery)
    # ============================================
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_username: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    rabbitmq_management_port: int = 15672
    
    # Celery Broker URL (RabbitMQ)
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    
    # Celery Result Backend (MongoDB)
    celery_result_backend: str = "mongodb://localhost:27017/legal_policy_analyzer"
    
    # ============================================
    # Celery Configuration
    # ============================================
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 600
    celery_task_soft_time_limit: int = 540
    celery_task_acks_late: bool = True
    celery_worker_prefetch_multiplier: int = 1
    celery_result_expires: int = 86400
    celery_task_max_retries: int = 3
    celery_task_default_retry_delay: int = 60
    
    # ============================================
    # API Configuration
    # ============================================
    api_title: str = "Legal Policy Analyzer API"
    api_version: str = "1.0.0"
    api_description: str = "تحليل سياسات المتاجر الإلكترونية للامتثال القانوني"
    
    # ============================================
    # CORS Configuration
    # ============================================
    allowed_origins: List[str] = ["*"]
    
    # ============================================
    # Security Settings
    # ============================================
    rate_limit_requests: int = 20
    rate_limit_window: int = 60
    rate_limit_block_duration: int = 15
    
    max_request_size: int = 10 * 1024 * 1024
    max_text_length: int = 50000
    min_text_length: int = 50
    
    # ============================================
    # AI Service Limits
    # ============================================
    max_daily_requests: int = 1000
    max_daily_tokens: int = 1000000
    ai_timeout: int = 120
    ai_max_retries: int = 3
    
    # ============================================
    # Circuit Breaker
    # ============================================
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 120
    
    # ============================================
    # Request Deduplication
    # ============================================
    deduplication_ttl: int = 300
    
    # ============================================
    # Idempotency Settings
    # ============================================
    idempotency_ttl: int = 86400
    idempotency_key_header: str = "X-Idempotency-Key"
    idempotency_enable: bool = True
    
    # ============================================
    # Graceful Degradation Settings
    # ============================================
    graceful_degradation_ttl: int = 604800  # 7 days
    graceful_degradation_enable: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()