"""
Security Middleware - طبقة حماية للـ API
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Callable
from app.safeguards import rate_limiter, content_filter
from app.logger import app_logger

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware للأمان والحماية
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # تسجيل الطلب
        start_time = time.time()
        client_ip = request.client.host
        path = request.url.path
        
        app_logger.info(f"📨 Incoming request: {request.method} {path} from {client_ip}")
        
        try:
            # تطبيق Rate Limiting (فقط لـ /api/ endpoints)
            if path.startswith("/api/"):
                is_limited, reason = rate_limiter.is_rate_limited(
                    identifier=client_ip,
                    max_requests=20,  # 20 طلبات
                    window_seconds=60,  # في الدقيقة
                    block_duration_minutes=15  # حظر لمدة 15 دقيقة
                )
                
                if is_limited:
                    app_logger.warning(f"🚫 Rate limit exceeded: {client_ip} - {reason}")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Too Many Requests",
                            "message": reason,
                            "retry_after": 900  # 15 minutes in seconds
                        }
                    )
                
                # عرض عدد الطلبات المتبقية
                remaining = rate_limiter.get_remaining_requests(client_ip, max_requests=20)
                app_logger.debug(f"Remaining requests for {client_ip}: {remaining}")
            
            # معالجة الطلب
            response = await call_next(request)
            
            # حساب مدة المعالجة
            process_time = time.time() - start_time
            
            # إضافة headers أمنية
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            app_logger.info(
                f"✅ Request completed: {request.method} {path} - "
                f"Status: {response.status_code} - "
                f"Duration: {process_time:.2f}s"
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            app_logger.error(
                f"❌ Request failed: {request.method} {path} - "
                f"Error: {str(e)} - "
                f"Duration: {process_time:.2f}s"
            )
            raise

class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware للتحكم في حجم الطلبات
    """
    
    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10 MB
        super().__init__(app)
        self.max_request_size = max_request_size
    
    async def dispatch(self, request: Request, call_next: Callable):
        # فحص حجم الطلب
        content_length = request.headers.get("content-length")
        
        if content_length:
            content_length = int(content_length)
            
            if content_length > self.max_request_size:
                app_logger.warning(
                    f"🚫 Request too large: {content_length} bytes from {request.client.host}"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload Too Large",
                        "message": f"حجم الطلب {content_length} بايت يتجاوز الحد المسموح {self.max_request_size} بايت",
                        "max_size": self.max_request_size
                    }
                )
        
        return await call_next(request)

class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware لأمان CORS
    """
    
    def __init__(self, app, allowed_origins: list = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["http://localhost:8000"]
    
    async def dispatch(self, request: Request, call_next: Callable):
        origin = request.headers.get("origin")
        
        # التحقق من Origin
        if origin and origin not in self.allowed_origins and "*" not in self.allowed_origins:
            app_logger.warning(f"🚫 Unauthorized origin: {origin}")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Origin غير مصرح به"
                }
            )
        
        return await call_next(request)