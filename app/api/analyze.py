"""
Analysis API Endpoints (with Celery integration)
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime

from app.models import PolicyAnalysisRequest
from app.celery_app.tasks import analyze_policy_task
from celery.result import AsyncResult
from app.celery_app.celery import celery_app
from app.services.idempotency_service import idempotency_service
from app.logger import app_logger

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze")
async def analyze_policy_async(
    request: PolicyAnalysisRequest,
    http_request: Request,
    x_idempotency_key: Optional[str] = Header(None),
    x_force_refresh: Optional[str] = Header(None)
):
    """
    Submit Policy Analysis Task (Async with Celery)
    Returns task_id immediately, analysis runs in background
    """
    client_ip = http_request.client.host
    app_logger.info(f"📨 New async analysis request - Shop: {request.shop_name} - IP: {client_ip}")
    
    # Generate or use idempotency key
    request_data = {
        "shop_name": request.shop_name,
        "shop_specialization": request.shop_specialization,
        "policy_type": request.policy_type.value,
        "policy_text": request.policy_text
    }
    
    if x_idempotency_key:
        idempotency_key = x_idempotency_key
    else:
        idempotency_key = idempotency_service.generate_key_from_request(request_data)
    
    # Check force refresh
    force_refresh = x_force_refresh and x_force_refresh.lower() == 'true'
    
    if force_refresh:
        app_logger.info(f"🔄 Force refresh requested - Clearing cache")
        await idempotency_service.delete_cached_result(idempotency_key)
    
    # Check cache first (quick response)
    if not force_refresh:
        cached_result = await idempotency_service.get_cached_result(idempotency_key)
        if cached_result:
            app_logger.info(f"✅ Cache HIT - Returning instantly")
            return {
                "status": "completed",
                "from_cache": True,
                "result": cached_result,
                "idempotency_key": idempotency_key
            }
    
    # Submit task to Celery
    app_logger.info(f"🚀 Submitting task to Celery - Key: {idempotency_key[:30]}...")
    
    task = analyze_policy_task.apply_async(
        args=[
            request.shop_name,
            request.shop_specialization,
            request.policy_type.value,
            request.policy_text,
            idempotency_key
        ],
        task_id=idempotency_key  # Use idempotency key as task ID
    )
    
    app_logger.info(f"✅ Task submitted - ID: {task.id}")
    
    return {
        "status": "pending",
        "task_id": task.id,
        "message": "تم إرسال الطلب للمعالجة",
        "idempotency_key": idempotency_key,
        "check_status_url": f"/api/task/{task.id}"
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get Task Status and Result
    """
    from celery.result import AsyncResult
    from app.celery_app.celery import celery_app
    
    app_logger.debug(f"📊 Status check for task: {task_id[:30]}...")
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.ready():
        # Task completed
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
            # Task failed
            app_logger.error(f"❌ Task {task_id[:30]} failed")
            
            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(result.info),
                "failed_at": datetime.utcnow().isoformat()
            }
    
    elif result.state == 'PENDING':
        # Task not started yet or doesn't exist
        app_logger.debug(f"⏳ Task {task_id[:30]} pending...")
        
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "في انتظار المعالجة..."
        }
    
    elif result.state == 'STARTED':
        # Task started
        app_logger.debug(f"🔄 Task {task_id[:30]} started")
        
        return {
            "status": "processing",
            "task_id": task_id,
            "progress": result.info,
            "message": "جاري المعالجة..."
        }
    
    elif result.state == 'PROGRESS':
        # Task in progress with updates
        app_logger.debug(f"🔄 Task {task_id[:30]} in progress")
        
        return {
            "status": "processing",
            "task_id": task_id,
            "progress": result.info,
            "message": result.info.get('status', 'جاري المعالجة...')
        }
    
    else:
        # Unknown state
        return {
            "status": result.state.lower(),
            "task_id": task_id,
            "info": str(result.info)
        }

@router.get("/task/{task_id}/stream")
async def satream_task_sttus(task_id: str, request: Request):
    """
    Streams task status updates using Server-Sent Events (SSE).
    This counts as ONLY 1 REQUEST for rate limiting purposes.
    """
    
    # Verify task exists first to avoid streaming 404s
    task = AsyncResult(task_id, app=celery_app)
    if task.state == 'PENDING' and not task.result:
        # Optional: Logic to handle invalid IDs, but PENDING is default for unknown IDs in Celery
        pass

    async def event_generator():
        """
        Generator that yields SSE formatted events:
        data: {"status": "...", "progress": ...} \n\n
        """
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                # Get latest status from Celery/Redis
                # Note: We re-instantiate AsyncResult to ensure fresh state fetching
                result = AsyncResult(task_id, app=celery_app)
                
                data = {
                    "task_id": task_id,
                    "status": result.status.lower(), # 'processing', 'completed', 'failed'
                    "progress": {},
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Construct the payload based on state
                if result.state == 'SUCCESS':
                    data["status"] = "completed"
                    data["result"] = result.get()
                    # Send final event and break loop
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
                
                else: # PENDING
                     data["status"] = "pending"
                     yield f"data: {json.dumps(data)}\n\n"

                # Wait before next check (Server-side polling)
                # This reduces load on Redis
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
            "X-Accel-Buffering": "no" # Crucial for Nginx proxies
        }
    )

@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a Running Task
    """
    from celery.result import AsyncResult
    from app.celery_app.celery import celery_app
    
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
    """
    Get All Active Tasks
    """
    from app.celery_app.celery import celery_app
    
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