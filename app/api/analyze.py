"""
Secure Analysis API - بدون headers قابلة للاستغلال
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime

from app.models import PolicyAnalysisRequest, ForceNewAnalysisRequest
from app.celery_app.tasks import analyze_policy_task
from celery.result import AsyncResult
from app.celery_app.celery import celery_app
from app.services.idempotency_service import idempotency_service
from app.logger import app_logger

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze")
async def analyze_policy_secure(
    request: PolicyAnalysisRequest,
    http_request: Request
):
    """
    ✅ Secure Analysis Endpoint with Complete Workflow
    
    Workflow:
    1. Generate idempotency_key from request body
    2. Check cache → if found → ask user
    3. Check pending tasks → if found → return existing task_id
    4. Check completed tasks → if found → retrieve & re-cache
    5. Submit new task only if needed
    
    - بدون headers قابلة للاستغلال
    - يعمل idempotency key من الـ body
    - checks كاملة قبل submit
    """
    client_ip = http_request.client.host
    app_logger.info(f"📨 New secure analysis request - Shop: {request.shop_name} - IP: {client_ip}")
    
    # 1. Generate idempotency key من الـ request body (SHA256 hash)
    request_data = {
        "shop_name": request.shop_name,
        "shop_specialization": request.shop_specialization,
        "policy_type": request.policy_type.value,
        "policy_text": request.policy_text
    }
    
    idempotency_key = idempotency_service.generate_key_from_request(request_data)
    app_logger.info(f"🔑 Generated idempotency key: {idempotency_key[:30]}...")
    
    # ═══════════════════════════════════════════════════════════
    # 2. CHECK CACHE FIRST (Highest Priority - Instant Return)
    # ═══════════════════════════════════════════════════════════
    app_logger.info(f"🔍 Step 1: Checking cache for key: {idempotency_key[:30]}...")
    cached_result = await idempotency_service.get_cached_result(idempotency_key)
    
    if cached_result:
        app_logger.info(f"✅ Cache HIT - Asking user for decision")
        
        # 🎯 المستخدم يقرر: استخدام القديم أو تحليل جديد
        return {
            "status": "found_existing",
            "message": "تم العثور على تحليل سابق لنفس السياسة",
            "result": cached_result,
            "idempotency_key": idempotency_key,
            "ask_user": True,  # ← Frontend يسأل المستخدم
            "options": {
                "use_existing": {
                    "label": "استخدام التحليل السابق",
                    "action": "use_cached",
                    "description": "التحليل جاهز ومجاني"
                },
                "create_new": {
                    "label": "إنشاء تحليل جديد",
                    "action": "force_new",
                    "endpoint": "/api/analyze/force-new",
                    "description": "تحليل جديد (قد يستغرق وقتًا)"
                }
            },
            "cached_at": cached_result.get('cache_timestamp', ''),
            "from_cache": True
        }
    
    app_logger.info(f"ℹ️ Cache MISS - Proceeding to check for pending tasks...")
    
    # ═══════════════════════════════════════════════════════════
    # 3. CHECK PENDING/RUNNING TASKS (Avoid Duplicate Submissions)
    # ═══════════════════════════════════════════════════════════
    from celery.result import AsyncResult
    from app.celery_app.celery import celery_app
    
    app_logger.info(f"⏳ Step 2: Checking for pending/running tasks...")
    existing_task = AsyncResult(idempotency_key, app=celery_app)
    
    # Check if task exists and is still running
    if existing_task.state in ['RECEIVED', 'STARTED', 'PROGRESS']:
        app_logger.info(
            f"⏳ Found existing {existing_task.state} task - "
            f"Returning existing task_id: {idempotency_key[:30]}..."
        )
        
        # ✅ Return existing task_id (مش نعمل task جديد!)
        return {
            "status": existing_task.state.lower(),
            "task_id": idempotency_key,
            "message": "يوجد طلب مطابق قيد المعالجة",
            "idempotency_key": idempotency_key,
            "check_status_url": f"/api/task/{idempotency_key}",
            "from_cache": False,
            "note": "تم العثور على طلب مطابق قيد التنفيذ - لن يتم إنشاء طلب جديد"
        }
    
    app_logger.info(f"ℹ️ No pending tasks found - Checking completed tasks...")
    
    # ═══════════════════════════════════════════════════════════
    # 4. CHECK COMPLETED TASKS (Retrieve from Celery Backend)
    # ═══════════════════════════════════════════════════════════
    if existing_task.state == 'SUCCESS':
        app_logger.warning(
            f"💾 Step 3: Task was successful but result not in cache - "
            f"Fetching from Celery result backend"
        )
        
        try:
            # Quick fetch from Celery backend (timeout 5s)
            task_result = existing_task.get(timeout=5)
            
            if task_result and isinstance(task_result, dict):
                result_data = task_result.get('result')
                
                if result_data:
                    # ✅ Re-cache the result for next time
                    await idempotency_service.store_result(idempotency_key, result_data)
                    
                    app_logger.info(f"✅ Retrieved result from Celery backend and re-cached")
                    
                    # سؤال المستخدم (زي لو كان في cache)
                    return {
                        "status": "found_existing",
                        "message": "تم العثور على تحليل سابق لنفس السياسة",
                        "result": result_data,
                        "idempotency_key": idempotency_key,
                        "ask_user": True,
                        "options": {
                            "use_existing": {
                                "label": "استخدام التحليل السابق",
                                "action": "use_cached",
                                "description": "التحليل جاهز ومجاني"
                            },
                            "create_new": {
                                "label": "إنشاء تحليل جديد",
                                "action": "force_new",
                                "endpoint": "/api/analyze/force-new",
                                "description": "تحليل جديد (قد يستغرق وقتًا)"
                            }
                        },
                        "from_cache": True,
                        "note": "تم استرجاع النتيجة من Celery backend"
                    }
        except Exception as e:
            app_logger.warning(
                f"⚠️ Failed to retrieve result from Celery backend: {str(e)} - "
                f"Will create new task"
            )
            # Continue to create new task
    
    # ═══════════════════════════════════════════════════════════
    # 5. SUBMIT NEW TASK (Only if no cache, no pending, no completed)
    # ═══════════════════════════════════════════════════════════
    app_logger.info(f"🚀 Step 4: No existing data found - Submitting NEW task to Celery")
    
    # Use idempotency_key as task_id for future deduplication
    task = analyze_policy_task.apply_async(
        args=[
            request.shop_name,
            request.shop_specialization,
            request.policy_type.value,
            request.policy_text,
            idempotency_key,
            False  # force_refresh = False دائمًا في هذا الـ endpoint
        ],
        task_id=idempotency_key  # ← Important: Use idempotency_key for deduplication
    )
    
    app_logger.info(f"✅ New task submitted - ID: {task.id}")
    
    return {
        "status": "pending",
        "task_id": task.id,
        "message": "تم إرسال الطلب للمعالجة",
        "idempotency_key": idempotency_key,
        "check_status_url": f"/api/task/{task.id}",
        "from_cache": False
    }


@router.post("/analyze/force-new")
async def force_new_analysis(
    request: ForceNewAnalysisRequest,
    http_request: Request
):
    """
    🔒 Force New Analysis - بحماية من الاستغلال
    
    Security Features:
    - يحتاج idempotency_key صالح (مطابق للـ request)
    - Rate limited بشدة (3 requests/hour per IP)
    - يتتبع كل IP وكل محاولة
    - يستخدم Pydantic model محترم مع validation كامل
    - يحذف الـ cache القديم قبل إنشاء task جديد
    
    Workflow:
    1. Check rate limit (3/hour)
    2. Validate idempotency_key matches request
    3. Delete old cache
    4. Cancel any pending tasks (optional but recommended)
    5. Create new unique task
    """
    client_ip = http_request.client.host
    
    app_logger.info(
        f"🔄 Force refresh request - Shop: {request.shop_name} - IP: {client_ip} - "
        f"Key: {request.idempotency_key[:30]}..."
    )
    
    # ═══════════════════════════════════════════════════════════
    # 1. CHECK RATE LIMIT (مشدد جدًا لهذا الـ endpoint)
    # ═══════════════════════════════════════════════════════════
    from app.safeguards import rate_limiter
    
    is_limited, reason = rate_limiter.is_rate_limited(
        identifier=f"force_refresh:{client_ip}",
        max_requests=3,  # 3 طلبات force refresh فقط
        window_seconds=3600,  # في الساعة
        block_duration_minutes=60  # حظر ساعة
    )
    
    if is_limited:
        app_logger.warning(
            f"🚫 Rate limit exceeded for force refresh - IP: {client_ip} - {reason}"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "تم تجاوز الحد المسموح",
                "message": reason,
                "retry_after": 3600,
                "remaining_attempts": 0
            }
        )
    
    # ═══════════════════════════════════════════════════════════
    # 2. VALIDATE IDEMPOTENCY KEY (يجب أن يطابق الـ request)
    # ═══════════════════════════════════════════════════════════
    request_data = {
        "shop_name": request.shop_name,
        "shop_specialization": request.shop_specialization,
        "policy_type": request.policy_type.value,
        "policy_text": request.policy_text
    }
    
    expected_key = idempotency_service.generate_key_from_request(request_data)
    
    if request.idempotency_key != expected_key:
        app_logger.error(
            f"❌ Invalid idempotency key - Expected: {expected_key[:30]}..., "
            f"Got: {request.idempotency_key[:30]}... - IP: {client_ip}"
        )
        
        # Track suspicious behavior
        # rate_limiter.track_suspicious_activity(
        #     identifier=f"invalid_key:{client_ip}",
        #     reason="Invalid idempotency key in force-new"
        # )
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid idempotency key",
                "message": "مفتاح التحليل غير صالح - تأكد من إرسال نفس البيانات",
                "hint": "يجب أن يطابق الـ idempotency_key البيانات المُرسلة"
            }
        )
    
    app_logger.info(f"✅ Idempotency key validated successfully")
    
    # ═══════════════════════════════════════════════════════════
    # 3. DELETE OLD CACHE (تنظيف النتائج القديمة)
    # ═══════════════════════════════════════════════════════════
    app_logger.info(f"🗑️ Deleting old cache for key: {request.idempotency_key[:30]}...")
    
    deletion_result = await idempotency_service.delete_cached_result(request.idempotency_key)
    
    if deletion_result:
        app_logger.info(f"✅ Old cache deleted successfully")
    else:
        app_logger.info(f"ℹ️ No cache found to delete (might be first analysis)")
    
    # ═══════════════════════════════════════════════════════════
    # 4. CANCEL PENDING TASKS (Optional - منع تعارض Tasks)
    # ═══════════════════════════════════════════════════════════
    from celery.result import AsyncResult
    from app.celery_app.celery import celery_app
    
    # Check if there's a pending task with the same idempotency_key
    existing_task = AsyncResult(request.idempotency_key, app=celery_app)
    
    if existing_task.state in ['STARTED', 'PROGRESS']:
        app_logger.warning(
            f"⚠️ Found existing {existing_task.state} task - "
            f"Attempting to revoke it before creating new one"
        )
        
        try:
            # Revoke the old task (terminate=True to kill it immediately)
            existing_task.revoke(terminate=True)
            app_logger.info(f"✅ Old task revoked successfully")
        except Exception as e:
            app_logger.warning(f"⚠️ Failed to revoke old task: {str(e)}")
            # Continue anyway - the new task will take priority
    
    # ═══════════════════════════════════════════════════════════
    # 5. CREATE NEW UNIQUE TASK (تجنب Celery Deduplication)
    # ═══════════════════════════════════════════════════════════
    import time
    
    # Generate unique task_id (millisecond precision)
    unique_task_id = f"{request.idempotency_key}_refresh_{int(time.time() * 1000)}"
    
    app_logger.info(f"🚀 Creating NEW task with unique ID: {unique_task_id[:40]}...")
    
    task = analyze_policy_task.apply_async(
        args=[
            request.shop_name,
            request.shop_specialization,
            request.policy_type.value,
            request.policy_text,
            request.idempotency_key,  # Original key for caching
            True  # force_refresh = True
        ],
        task_id=unique_task_id,  # Unique ID to bypass Celery cache
        priority=5  # Higher priority for force refresh (0-10, default is 6)
    )
    
    app_logger.info(
        f"✅ Force refresh task submitted successfully - "
        f"Task ID: {task.id} - Shop: {request.shop_name}"
    )
    
    # Track successful force refresh
    # rate_limiter.track_successful_request(
    #     identifier=f"force_refresh:{client_ip}",
    #     metadata={
    #         "shop_name": request.shop_name,
    #         "policy_type": request.policy_type.value,
    #         "task_id": task.id
    #     }
    # )
    
    return {
        "status": "pending",
        "task_id": task.id,
        "message": "تم إنشاء تحليل جديد بنجاح",
        "idempotency_key": request.idempotency_key,
        "check_status_url": f"/api/task/{task.id}",
        "force_refresh": True,
        "from_cache": False,
        "estimated_time": "1-2 دقيقة",
        "note": "سيتم حذف التحليل القديم واستبداله بالجديد"
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get Task Status and Result
    """
    app_logger.debug(f"📊 Status check for task: {task_id[:30]}...")
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.ready():
        if result.successful():
            task_result = result.get()
            
            app_logger.info(f"✅ Task {task_id[:30]} completed successfully")
            
            return {
                "status": "completed",
                "task_id": task_id,
                "result": task_result.get('result') if task_result.get('success') else None,
                "from_cache": task_result.get('from_cache', False),
                "success": task_result.get('success', True),
                "error": task_result.get('error'),
                "completed_at": datetime.utcnow().isoformat()
            }
        else:
            app_logger.error(f"❌ Task {task_id[:30]} failed")
            
            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(result.info),
                "failed_at": datetime.utcnow().isoformat()
            }
    
    elif result.state == 'PENDING':
        app_logger.debug(f"⏳ Task {task_id[:30]} pending...")
        
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "في انتظار المعالجة..."
        }
    
    elif result.state == 'STARTED':
        app_logger.debug(f"🔄 Task {task_id[:30]} started")
        
        return {
            "status": "processing",
            "task_id": task_id,
            "progress": result.info,
            "message": "جاري المعالجة..."
        }
    
    elif result.state == 'PROGRESS':
        app_logger.debug(f"🔄 Task {task_id[:30]} in progress")
        
        return {
            "status": "processing",
            "task_id": task_id,
            "progress": result.info,
            "message": result.info.get('status', 'جاري المعالجة...')
        }
    
    else:
        return {
            "status": result.state.lower(),
            "task_id": task_id,
            "info": str(result.info)
        }


@router.get("/task/{task_id}/stream")
async def stream_task_status(task_id: str, request: Request):
    """
    Streams task status updates using Server-Sent Events (SSE).
    """
    
    task = AsyncResult(task_id, app=celery_app)
    if task.state == 'PENDING' and not task.result:
        pass

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                result = AsyncResult(task_id, app=celery_app)
                
                data = {
                    "task_id": task_id,
                    "status": result.status.lower(),
                    "progress": {},
                    "timestamp": datetime.utcnow().isoformat()
                }

                if result.state == 'SUCCESS':
                    data["status"] = "completed"
                    data["result"] = result.get()
                    yield f"data: {json.dumps(data)}\n\n"
                    break
                
                elif result.state == 'FAILURE':
                    data["status"] = "failed"
                    data["error"] = str(result.info)
                    yield f"data: {json.dumps(data)}\n\n"
                    break
                
                elif result.state in ['STARTED', 'PROGRESS']:
                    data["status"] = "processing"
                    data["progress"] = result.info if isinstance(result.info, dict) else {}
                    yield f"data: {json.dumps(data)}\n\n"
                
                else:
                     data["status"] = "pending"
                     yield f"data: {json.dumps(data)}\n\n"

                await asyncio.sleep(2)

        except Exception as e:
            app_logger.error(f"Stream error for {task_id}: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a Running Task"""
    app_logger.info(f"🛑 Cancel request for task: {task_id[:30]}...")
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state in ['PENDING', 'STARTED', 'PROGRESS']:
        result.revoke(terminate=True)
        app_logger.info(f"✅ Task {task_id[:30]} cancelled")
        
        return {
            "status": "cancelled",
            "task_id": task_id,
            "message": "تم إلغاء المهمة"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن إلغاء المهمة في الحالة: {result.state}"
        )


@router.get("/tasks/active")
async def get_active_tasks():
    """Get All Active Tasks"""
    inspector = celery_app.control.inspect()
    
    active = inspector.active()
    scheduled = inspector.scheduled()
    reserved = inspector.reserved()
    
    return {
        "active": active or {},
        "scheduled": scheduled or {},
        "reserved": reserved or {},
        "timestamp": datetime.utcnow().isoformat()
    }