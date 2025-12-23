import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
from datetime import datetime
import webbrowser
import time

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import json

from app.config import get_settings
from app.models import PolicyAnalysisRequest, AnalysisResponse, RegenerationRequest
from app.services.analyzer_service import AnalyzerService
from app.services.idempotency_service import idempotency_service
from app.logger import app_logger
from app.middleware import SecurityMiddleware, RequestSizeMiddleware

settings = get_settings()

# ============================================
# إضافة: HTML Server على Port منفصل
# ============================================
class CustomHTMLHandler(SimpleHTTPRequestHandler):
    """Handler مخصص لخدمة ملفات HTML وملفات static"""
    
    def __init__(self, *args, **kwargs):
        # بدون تحديد directory عشان نقدر نتحكم يدوياً
        super().__init__(*args, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        SimpleHTTPRequestHandler.end_headers(self)
    
    def translate_path(self, path):
        """ترجمة المسار للملف الصحيح"""
        # إزالة query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        
        # تحويل المسار
        if path == '/' or path == '':
            # الصفحة الرئيسية من templates
            return os.path.join(os.getcwd(), 'templates', 'index.html')
        elif path.startswith('/static/'):
            # ملفات static
            return os.path.join(os.getcwd(), path[1:])  # إزالة / من البداية
        else:
            # ملفات أخرى من templates
            return os.path.join(os.getcwd(), 'templates', path[1:])
    
    def log_message(self, format, *args):
        app_logger.info(f"[HTML Server] {format % args}")


def run_html_server(port=5000):
    """تشغيل خادم HTML منفصل"""
    try:
        templates_path = Path("templates")
        if not templates_path.exists():
            app_logger.error("❌ Templates folder not found!")
            return
        
        server = HTTPServer(('0.0.0.0', port), CustomHTMLHandler)
        app_logger.info(f"🌐 HTML Server running at http://localhost:{port}")
        
        # فتح المتصفح بعد ثانيتين من بدء السيرفر
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

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(SecurityMiddleware)
app.add_middleware(RequestSizeMiddleware, max_request_size=10 * 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=3600
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

analyzer_service = AnalyzerService()

@app.on_event("startup")
async def startup_event():
    """حدث بدء التشغيل"""
    app_logger.info("🚀 Legal Policy Analyzer API Starting...")
    app_logger.info(f"📝 Version: {settings.api_version}")
    app_logger.info(f"🪶 OpenAI Light Model: {settings.openai_light_model} (Stage 1)")
    app_logger.info(f"🔥 OpenAI Heavy Model: {settings.openai_heavy_model} (Stage 2-4)")
    
    # ============================================
    # إضافة: بدء HTML Server في Thread منفصل
    # ============================================
    html_thread = threading.Thread(target=run_html_server, args=(5000,), daemon=True)
    html_thread.start()
    app_logger.info("🎯 HTML Server thread started on port 5000")
    # ============================================
    
    # تهيئة Redis للـ Idempotency
    if settings.idempotency_enable:
        try:
            await idempotency_service.connect()
            app_logger.info("🔑 Idempotency service enabled")
        except Exception as e:
            app_logger.warning(f"⚠️ Idempotency service failed to start: {str(e)}")
            app_logger.warning("⚠️ Continuing without idempotency protection")
    else:
        app_logger.info("ℹ️  Idempotency service disabled")
    
    app_logger.info("✅ Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """حدث إيقاف التشغيل"""
    app_logger.info("🛑 Legal Policy Analyzer API Shutting down...")
    
    # إغلاق اتصال Redis
    await idempotency_service.disconnect()
    
    app_logger.info("✅ Application stopped successfully")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """الصفحة الرئيسية"""
    app_logger.debug(f"Serving homepage to {request.client.host}")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """فحص صحة الخادم"""
    stats = await idempotency_service.get_stats()
    return {
        "status": "healthy",
        "service": "Legal Policy Analyzer",
        "idempotency": stats
    }


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_policy(
    request: PolicyAnalysisRequest, 
    http_request: Request,
    x_idempotency_key: Optional[str] = Header(None),
    x_force_refresh: Optional[str] = Header(None)
):
    """
    نقطة النهاية الرئيسية لتحليل السياسات - مع Idempotency و Caching
    """
    client_ip = http_request.client.host
    app_logger.info(f"📨 New analysis request - Shop: {request.shop_name} - IP: {client_ip}")
    
    # ============================================
    # Stage 1: توليد أو استخدام Idempotency Key
    # ============================================
    request_data = {
        "shop_name": request.shop_name,
        "shop_specialization": request.shop_specialization,
        "policy_type": request.policy_type.value,
        "policy_text": request.policy_text
    }
    
    if x_idempotency_key:
        idempotency_key = x_idempotency_key
        app_logger.info(f"🔑 Using provided idempotency key: {idempotency_key[:16]}...")
    else:
        idempotency_key = idempotency_service.generate_key_from_request(request_data)
        app_logger.info(f"🔑 Generated idempotency key: {idempotency_key[:30]}...")
    
    # ============================================
    # Stage 1.5: التحقق من Force Refresh
    # ============================================
    force_refresh = x_force_refresh and x_force_refresh.lower() == 'true'
    
    if force_refresh:
        app_logger.info(f"🔄 Force refresh requested - Clearing cache for key: {idempotency_key[:30]}...")
        await idempotency_service.delete_cached_result(idempotency_key)
    
    # ============================================
    # Stage 2: التحقق من وجود نتيجة محفوظة (Cache Check)
    # ============================================
    cached_result = None
    if not force_refresh:
        cached_result = await idempotency_service.get_cached_result(idempotency_key)
    
    if cached_result:
        app_logger.info(f"✅ Cache HIT - Returning cached result for Shop: {request.shop_name}")
        
        try:
            # 🔥 CRITICAL: تأكد من وجود from_cache في البيانات
            cached_result["from_cache"] = True
            
            # تحويل النتيجة لـ Object للتحقق من سلامتها
            cached_response = AnalysisResponse(**cached_result)
            
            # استخراج وقت الحفظ
            timestamp = cached_result.get("cache_timestamp", datetime.utcnow().isoformat())
            
            app_logger.info(f"📦 Sending cached response with headers - Key: {idempotency_key[:30]}")
            
            # 🔥 CRITICAL: إرجاع Response مع Headers كاملة
            return JSONResponse(
                content=cached_response.model_dump(),
                headers={
                    "X-Cache-Status": "HIT",
                    "X-Cache-Timestamp": timestamp,
                    "X-Idempotency-Key": idempotency_key,
                    "Access-Control-Expose-Headers": "X-Cache-Status, X-Cache-Timestamp, X-Idempotency-Key"
                }
            )
        except Exception as e:
            app_logger.error(f"Error parsing cached result: {str(e)}")
            await idempotency_service.delete_cached_result(idempotency_key)
    
    app_logger.info(f"📊 Cache MISS - Proceeding with new analysis")
    
    # ============================================
    # Stage 3: التحقق من طلب قيد التنفيذ (In-Progress Check)
    # ============================================
    in_progress = await idempotency_service.check_in_progress(idempotency_key)
    
    if in_progress:
        app_logger.warning(f"⚠️ Request already in progress - Shop: {request.shop_name}")
        raise HTTPException(
            status_code=409,
            detail="يتم معالجة نفس الطلب حالياً. الرجاء الانتظار قليلاً والمحاولة مرة أخرى.",
            headers={
                "X-Idempotency-Key": idempotency_key,
                "Access-Control-Expose-Headers": "X-Idempotency-Key"
            }
        )
    
    # ============================================
    # Stage 4: وضع علامة "قيد التنفيذ" (Acquire Lock)
    # ============================================
    lock_acquired = await idempotency_service.mark_in_progress(
        idempotency_key,
        timeout=300
    )
    
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="فشل في الحصول على قفل المعالجة. الرجاء المحاولة مرة أخرى.",
            headers={
                "X-Idempotency-Key": idempotency_key,
                "Access-Control-Expose-Headers": "X-Idempotency-Key"
            }
        )
    
    try:
        # ============================================
        # Stage 5: تنفيذ التحليل الفعلي
        # ============================================
        app_logger.info(f"🔬 Starting new analysis for Shop: {request.shop_name}")
        result = await analyzer_service.analyze_policy(request)
        
        # ============================================
        # Stage 6: حفظ النتيجة في الـ cache
        # ============================================
        result_dict = result.model_dump()
        
        # 🔥 CRITICAL: تأكد من إضافة from_cache
        result_dict["from_cache"] = False
        
        # إضافة Timestamp الحالي
        current_timestamp = datetime.utcnow().isoformat()
        result_dict["cache_timestamp"] = current_timestamp
        
        if result.success:
            await idempotency_service.store_result(idempotency_key, result_dict)
            app_logger.info(f"💾 Analysis completed and cached - Shop: {request.shop_name}")
        else:
            app_logger.warning(f"⚠️ Analysis completed with issues - Shop: {request.shop_name}")
        
        app_logger.info(f"📤 Sending fresh response with headers - Key: {idempotency_key[:30]}")
        
        # 🔥 CRITICAL: إرجاع Response مع Headers كاملة
        return JSONResponse(
            content=result_dict,
            headers={
                "X-Cache-Status": "MISS",
                "X-Cache-Timestamp": current_timestamp,
                "X-Idempotency-Key": idempotency_key,
                "Access-Control-Expose-Headers": "X-Cache-Status, X-Cache-Timestamp, X-Idempotency-Key"
            }
        )
        
    except ValueError as e:
        app_logger.warning(f"⚠️ Validation error - Shop: {request.shop_name} - Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"خطأ في البيانات المدخلة: {str(e)}",
            headers={
                "X-Idempotency-Key": idempotency_key,
                "Access-Control-Expose-Headers": "X-Idempotency-Key"
            }
        )
        
    except Exception as e:
        app_logger.error(f"❌ Analysis failed - Shop: {request.shop_name} - Error: {str(e)}")
        
        error_msg = str(e)
        status_code = 500
        
        if "تجاوز الحد اليومي" in error_msg or "Daily limit" in error_msg:
            status_code = 429
        elif "timeout" in error_msg.lower() or "انتهت مهلة" in error_msg:
            status_code = 504
        elif "الخدمة معطلة" in error_msg:
            status_code = 503
        
        raise HTTPException(
            status_code=status_code,
            detail=f"حدث خطأ أثناء التحليل: {str(e)}",
            headers={
                "X-Idempotency-Key": idempotency_key,
                "Access-Control-Expose-Headers": "X-Idempotency-Key"
            }
        )
        
    finally:
        # ============================================
        # Stage 7: إزالة علامة "قيد التنفيذ" (Release Lock)
        # ============================================
        await idempotency_service.clear_in_progress(idempotency_key)
        app_logger.info(f"🔓 Lock released for key: {idempotency_key[:30]}")


@app.post("/api/export-report")
async def export_report(report_data: dict):
    """تصدير التقرير بصيغة JSON"""
    app_logger.info("📥 Report export requested")
    try:
        return JSONResponse(
            content=report_data,
            headers={
                "Content-Disposition": "attachment; filename=compliance_report.json"
            }
        )
    except Exception as e:
        app_logger.error(f"❌ Report export failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"حدث خطأ أثناء التصدير: {str(e)}"
        )

@app.get("/api/policy-types")
async def get_policy_types():
    """الحصول على قائمة أنواع السياسات المتاحة"""
    app_logger.debug("Policy types list requested")
    return {
        "policy_types": [
            {
                "value": "سياسات الاسترجاع و الاستبدال",
                "label": "سياسات الاسترجاع والاستبدال",
                "description": "سياسات إرجاع واستبدال المنتجات وحقوق المستهلك"
            },
            {
                "value": "سياسة الحساب و الخصوصية",
                "label": "سياسة الحساب والخصوصية",
                "description": "سياسات حماية البيانات الشخصية وخصوصية المستخدم"
            },
            {
                "value": "سياسة الشحن و التوصيل",
                "label": "سياسة الشحن والتوصيل",
                "description": "سياسات التوصيل والشحن ومسؤوليات المتجر"
            }
        ]
    }

@app.post("/api/regenerate-only")
async def regenerate_policy_only(
    request: RegenerationRequest, 
    http_request: Request,
    x_idempotency_key: Optional[str] = Header(None)
):
    """
    إعادة كتابة السياسة فقط (بدون تحليل كامل) - مع Idempotency
    """
    from app.models import ImprovedPolicyResult, ImprovementDetail
    from app.prompts.policy_generator import get_policy_regeneration_prompt
    
    client_ip = http_request.client.host
    app_logger.info(f"📝 Regeneration-only request - Shop: {request.shop_name} - IP: {client_ip}")
    
    # توليد idempotency key
    request_data = {
        "type": "regenerate",
        "shop_name": request.shop_name,
        "policy_type": request.policy_type.value,
        "original_policy": request.original_policy[:1000]
    }
    
    if x_idempotency_key:
        idempotency_key = x_idempotency_key
    else:
        idempotency_key = idempotency_service.generate_key_from_request(request_data)
    
    # التحقق من الـ cache
    cached_result = await idempotency_service.get_cached_result(idempotency_key)
    if cached_result:
        return JSONResponse(
            content=cached_result,
            headers={
                "X-Cache-Status": "HIT",
                "X-Idempotency-Key": idempotency_key
            }
        )
    
    # وضع علامة قيد التنفيذ
    lock_acquired = await idempotency_service.mark_in_progress(idempotency_key)
    if not lock_acquired:
        raise HTTPException(status_code=409, detail="يتم معالجة نفس الطلب")
    
    try:
        result = await analyzer_service.ai_service.regenerate_policy(
            request.shop_name,
            request.shop_specialization,
            request.policy_type.value,
            request.original_policy,
            request.compliance_report,
            get_policy_regeneration_prompt
        )
        
        improvements = [
            ImprovementDetail(**improvement)
            for improvement in result.get("improvements_made", [])
        ]
        
        improved_result = ImprovedPolicyResult(
            improved_policy=result.get("improved_policy", ""),
            improvements_made=improvements,
            compliance_enhancements=result.get("compliance_enhancements", []),
            structure_improvements=result.get("structure_improvements", []),
            estimated_new_compliance=result.get("estimated_new_compliance", 95),
            key_additions=result.get("key_additions", []),
            notes=result.get("notes")
        )
        
        response_data = {
            "success": True,
            "improved_policy": improved_result.model_dump()
        }
        
        # حفظ في الـ cache
        await idempotency_service.store_result(idempotency_key, response_data)
        
        app_logger.info(f"✅ Regeneration completed - Shop: {request.shop_name}")
        
        return JSONResponse(
            content=response_data,
            headers={
                "X-Cache-Status": "MISS",
                "X-Idempotency-Key": idempotency_key
            }
        )
        
    except Exception as e:
        app_logger.error(f"❌ Regeneration failed - Shop: {request.shop_name} - Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"حدث خطأ أثناء إعادة الكتابة: {str(e)}"
        )
    finally:
        await idempotency_service.clear_in_progress(idempotency_key)

@app.get("/api/idempotency-stats")
async def get_idempotency_stats():
    """الحصول على إحصائيات الـ Idempotency"""
    stats = await idempotency_service.get_stats()
    return stats

if __name__ == "__main__":
    import uvicorn
    app_logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)