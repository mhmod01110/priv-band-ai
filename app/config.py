from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # ============================================
    # AI Provider Selection
    # ============================================
    ai_provider: str = "openai"  # "openai" أو "gemini"
    
    # ============================================
    # OpenAI Configuration - Light Model (للمهام السهلة)
    # ============================================
    openai_api_key: str = ""
    openai_light_model: str = "gpt-4o-mini"  # موديل خفيف للـ Stage 1
    openai_light_temperature: float = 0.2
    openai_light_max_tokens: int = 2000
    
    # OpenAI Heavy Model (للمهام الصعبة)
    openai_heavy_model: str = "gpt-4o"  # موديل قوي للـ Stage 2-4
    openai_heavy_temperature: float = 0.3
    openai_heavy_max_tokens: int = 16000
    
    # ============================================
    # Gemini Configuration - Light Model (للمهام السهلة)
    # ============================================
    gemini_api_key: str = ""
    gemini_light_model: str = "gemini-1.5-flash"  # موديل خفيف للـ Stage 1
    gemini_light_temperature: float = 0.2
    gemini_light_max_tokens: int = 2000
    
    # Gemini Heavy Model (للمهام الصعبة)
    gemini_heavy_model: str = "gemini-2.0-flash-exp"  # موديل قوي للـ Stage 2-4
    gemini_heavy_temperature: float = 0.3
    gemini_heavy_max_tokens: int = 16000
    
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
    # Redis Configuration for Idempotency
    # ============================================
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_ssl: bool = False
    redis_decode_responses: bool = True
    
    # ============================================
    # Idempotency Settings
    # ============================================
    idempotency_ttl: int = 86400  # 24 hours
    idempotency_key_header: str = "X-Idempotency-Key"
    idempotency_enable: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()