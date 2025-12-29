import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import webbrowser
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.services.idempotency_service import idempotency_service
from app.logger import app_logger
from app.middleware import SecurityMiddleware, RequestSizeMiddleware

# Import new API routers
from app.api.analyze import router as analyze_router

settings = get_settings()

# ============================================
# HTML Server (unchanged)
# ============================================
class CustomHTMLHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        SimpleHTTPRequestHandler.end_headers(self)
    
    def translate_path(self, path):
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        
        if path == '/' or path == '':
            return os.path.join(os.getcwd(), 'templates', 'index.html')
        elif path.startswith('/static/'):
            return os.path.join(os.getcwd(), path[1:])
        else:
            return os.path.join(os.getcwd(), 'templates', path[1:])
    
    def log_message(self, format, *args):
        app_logger.info(f"[HTML Server] {format % args}")


def run_html_server(port=5000):
    try:
        templates_path = Path("templates")
        if not templates_path.exists():
            app_logger.error("❌ Templates folder not found!")
            return
        
        server = HTTPServer(('0.0.0.0', port), CustomHTMLHandler)
        app_logger.info(f"🌐 HTML Server running at http://localhost:{port}")
        
        def open_browser():
            time.sleep(2)
            webbrowser.open(f'http://localhost:{port}')
            app_logger.info(f"🌍 Browser opened automatically")
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        server.serve_forever()
        
    except Exception as e:
        app_logger.error(f"❌ HTML Server failed to start: {str(e)}")

# ============================================
# FastAPI Application
# ============================================
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(RequestSizeMiddleware, max_request_size=10 * 1024 * 1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(analyze_router)

# ============================================
# Startup & Shutdown Events
# ============================================
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    app_logger.info("🚀 Legal Policy Analyzer API Starting...")
    app_logger.info(f"📝 Version: {settings.api_version}")
    app_logger.info(f"🤖 AI Provider: {settings.ai_provider}")
    app_logger.info(f"🔥 Celery Integration: ENABLED")
    
    # Start HTML Server
    html_thread = threading.Thread(target=run_html_server, args=(5000,), daemon=True)
    html_thread.start()
    app_logger.info("🎯 HTML Server thread started on port 5000")
    
    # Initialize Redis for Idempotency
    if settings.idempotency_enable:
        try:
            await idempotency_service.connect()
            app_logger.info("🔑 Idempotency service enabled")
        except Exception as e:
            app_logger.warning(f"⚠️ Idempotency service failed: {str(e)}")
    
    app_logger.info("✅ Application started successfully")
    app_logger.info("=" * 80)
    app_logger.info("📋 ENDPOINTS:")
    app_logger.info("   POST /api/analyze - Submit analysis task")
    app_logger.info("   GET  /api/task/{task_id} - Check task status")
    app_logger.info("   DELETE /api/task/{task_id} - Cancel task")
    app_logger.info("   GET  /api/tasks/active - View active tasks")
    app_logger.info("   GET  /health - Health check")
    app_logger.info("   GET  /docs - API documentation")
    app_logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    app_logger.info("🛑 Legal Policy Analyzer API Shutting down...")
    await idempotency_service.disconnect()
    app_logger.info("✅ Application stopped successfully")


# ============================================
# Basic Endpoints
# ============================================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Homepage"""
    app_logger.debug(f"Serving homepage to {request.client.host}")
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from celery.result import AsyncResult
    from app.celery_app.celery import celery_app
    
    # Check Celery workers
    try:
        inspector = celery_app.control.inspect()
        active_workers = inspector.active()
        celery_healthy = active_workers is not None and len(active_workers) > 0
    except:
        celery_healthy = False
    
    # Check Redis
    stats = await idempotency_service.get_stats()
    redis_healthy = stats.get('connected', False)
    
    return {
        "status": "healthy" if (celery_healthy and redis_healthy) else "degraded",
        "service": "Legal Policy Analyzer",
        "celery": {
            "status": "healthy" if celery_healthy else "unhealthy",
            "workers": len(active_workers) if active_workers else 0
        },
        "redis": {
            "status": "healthy" if redis_healthy else "unhealthy",
            "idempotency": stats
        }
    }


@app.get("/api/info")
async def api_info():
    """API Information"""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "ai_provider": settings.ai_provider,
        "celery_enabled": True,
        "features": {
            "async_analysis": True,
            "idempotency": settings.idempotency_enable,
            "caching": True,
            "task_monitoring": True,
            "progress_tracking": True
        }
    }


# ============================================
# Main Entry Point
# ============================================
if __name__ == "__main__":
    import uvicorn
    app_logger.info("Starting uvicorn server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )