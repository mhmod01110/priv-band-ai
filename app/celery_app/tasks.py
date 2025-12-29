"""
Celery Task Definitions
All long-running analysis tasks
"""
import asyncio
from datetime import datetime, timedelta
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, Any

from app.celery_app.celery import celery_app
from app.models import PolicyAnalysisRequest, PolicyType
from app.services.analyzer_service import AnalyzerService
from app.services.idempotency_service import idempotency_service
from app.logger import app_logger
from app.config import get_settings

settings = get_settings()


class AsyncTask(Task):
    """
    Base Task class that handles async/await properly
    """
    def __call__(self, *args, **kwargs):
        # Run async functions in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.run(*args, **kwargs))
        finally:
            loop.close()


@celery_app.task(
    base=AsyncTask,
    bind=True,
    name='app.celery_app.tasks.analyze_policy_task',
    max_retries=3,
    soft_time_limit=540,  # 9 minutes
    time_limit=600  # 10 minutes hard limit
)
async def analyze_policy_task(
    self,
    shop_name: str,
    shop_specialization: str,
    policy_type: str,
    policy_text: str,
    idempotency_key: str = None
) -> Dict[str, Any]:
    """
    Main Policy Analysis Task (Async)
    
    Args:
        self: Task instance
        shop_name: Shop name
        shop_specialization: Shop specialization
        policy_type: Policy type
        policy_text: Policy text
        idempotency_key: Idempotency key for caching
    
    Returns:
        Analysis result dictionary
    """
    app_logger.info(
        f"🚀 [Celery Task {self.request.id}] Starting analysis for: {shop_name}"
    )
    
    try:
        # Update task state to STARTED
        self.update_state(
            state='STARTED',
            meta={
                'current': 0,
                'total': 4,
                'status': 'بدء التحليل...',
                'shop_name': shop_name
            }
        )
        
        # Initialize Redis connection
        await idempotency_service.connect()
        
        # Check cache first
        if idempotency_key:
            cached_result = await idempotency_service.get_cached_result(idempotency_key)
            if cached_result:
                app_logger.info(f"✅ [Task {self.request.id}] Cache HIT")
                return {
                    'success': True,
                    'from_cache': True,
                    'result': cached_result
                }
        
        # Create request object
        request = PolicyAnalysisRequest(
            shop_name=shop_name,
            shop_specialization=shop_specialization,
            policy_type=PolicyType(policy_type),
            policy_text=policy_text
        )
        
        # Stage 1: Policy Match
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': 4,
                'status': 'التحقق من مطابقة السياسة...',
                'shop_name': shop_name
            }
        )
        
        # Initialize analyzer service
        analyzer_service = AnalyzerService(provider=settings.ai_provider)
        
        # Stage 2: Compliance Analysis
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'status': 'تحليل الامتثال القانوني...',
                'shop_name': shop_name
            }
        )
        
        # Perform analysis
        result = await analyzer_service.analyze_policy(request)
        
        # Stage 3: Policy Regeneration (if needed)
        if result.compliance_report and result.compliance_report.overall_compliance_ratio < 95:
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 3,
                    'total': 4,
                    'status': 'إعادة كتابة السياسة المحسّنة...',
                    'shop_name': shop_name
                }
            )
        
        # Stage 4: Finalization
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 4,
                'total': 4,
                'status': 'إنهاء التحليل...',
                'shop_name': shop_name
            }
        )
        
        # Convert result to dict
        result_dict = result.model_dump()
        result_dict['from_cache'] = False
        result_dict['task_id'] = self.request.id
        result_dict['timestamp'] = datetime.utcnow().isoformat()
        
        # Cache the result
        if idempotency_key and result.success:
            await idempotency_service.store_result(idempotency_key, result_dict)
            app_logger.info(f"💾 [Task {self.request.id}] Result cached")
        
        app_logger.info(
            f"✅ [Task {self.request.id}] Analysis completed - "
            f"Compliance: {result.compliance_report.overall_compliance_ratio if result.compliance_report else 0}%"
        )
        
        return {
            'success': True,
            'from_cache': False,
            'result': result_dict
        }
        
    except SoftTimeLimitExceeded:
        app_logger.error(f"⏱️ [Task {self.request.id}] Soft time limit exceeded")
        return {
            'success': False,
            'error': 'تجاوز الوقت المسموح للتحليل',
            'error_type': 'timeout'
        }
        
    except Exception as e:
        app_logger.error(f"❌ [Task {self.request.id}] Error: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            app_logger.info(f"🔄 [Task {self.request.id}] Retrying... ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }
    
    finally:
        # Cleanup
        await idempotency_service.disconnect()


@celery_app.task(
    name='app.celery_app.tasks.regenerate_policy_task',
    max_retries=2,
    soft_time_limit=300,
    time_limit=360
)
def regenerate_policy_task(
    shop_name: str,
    shop_specialization: str,
    policy_type: str,
    original_policy: str,
    compliance_report: dict
) -> Dict[str, Any]:
    """
    Standalone Policy Regeneration Task
    """
    from app.services.analyzer_service import AnalyzerService
    from app.prompts.policy_generator import get_policy_regeneration_prompt
    
    app_logger.info(f"🚀 Regenerating policy for: {shop_name}")
    
    try:
        # Run async regeneration
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        analyzer = AnalyzerService()
        result = loop.run_until_complete(
            analyzer.ai_service.regenerate_policy(
                shop_name,
                shop_specialization,
                policy_type,
                original_policy,
                compliance_report,
                get_policy_regeneration_prompt
            )
        )
        
        loop.close()
        
        return {
            'success': True,
            'improved_policy': result
        }
        
    except Exception as e:
        app_logger.error(f"❌ Regeneration failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(name='app.celery_app.tasks.cleanup_old_results')
def cleanup_old_results():
    """
    Periodic task to cleanup old cached results
    Runs every hour via Celery Beat
    """
    app_logger.info("🧹 Running cleanup of old results...")
    
    try:
        # Connect to Redis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(idempotency_service.connect())
        
        # Logic to cleanup old keys (optional implementation)
        # You can implement custom cleanup logic here
        
        loop.run_until_complete(idempotency_service.disconnect())
        loop.close()
        
        app_logger.info("✅ Cleanup completed")
        return {'status': 'success', 'message': 'Cleanup completed'}
        
    except Exception as e:
        app_logger.error(f"❌ Cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='app.celery_app.tasks.health_check')
def health_check():
    """
    Health check task for monitoring
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker_id': health_check.request.id
    }