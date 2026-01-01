"""
Celery Task Definitions
All long-running analysis tasks
"""
import asyncio
from datetime import datetime, timedelta
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, Any, Callable, Optional

from app.celery_app.celery import celery_app
from app.models import (
    PolicyAnalysisRequest, 
    PolicyType, 
    PolicyMatchResult,
    AnalysisResponse
)
from app.services.analyzer_service import AnalyzerService
from app.services.idempotency_service import idempotency_service
from app.services.graceful_degradation import graceful_degradation_service
from app.logger import app_logger
from app.config import get_settings

# Import stage classes
from app.celery_app.stages import (
    Stage0Validation,
    Stage1AICheck,
    Stage2CacheRetrieval,
    Stage3Compliance,
    Stage4Regeneration,
    Stage5Finalization
)

settings = get_settings()


# ============================================
# Stage Configuration
# ============================================
# 
# Stages are now OOP classes, each in its own file.
# To add a new stage:
#   1. Create a new file in app/celery_app/stages/ (e.g., stage_X_name.py)
#   2. Create a class inheriting from BaseStage
#   3. Implement required properties and methods
#   4. Add the stage class to this list
#
# To remove a stage:
#   1. Remove from this list
#   2. Optionally delete the stage file
#
# Stages are instantiated with context when executed
STAGE_CLASSES = [
    Stage0Validation,
    Stage1AICheck,
    Stage2CacheRetrieval,
    Stage3Compliance,
    Stage4Regeneration,
    Stage5Finalization,
]


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


class StageContext:
    """
    Context object to pass data between stages
    """
    def __init__(self, task_instance, shop_name: str, shop_specialization: str, 
                 policy_type: str, policy_text: str, idempotency_key: str = None):
        self.task = task_instance
        self.shop_name = shop_name
        self.shop_specialization = shop_specialization
        self.policy_type = policy_type
        self.policy_text = policy_text
        self.idempotency_key = idempotency_key
        self.request = PolicyAnalysisRequest(
            shop_name=shop_name,
            shop_specialization=shop_specialization,
            policy_type=PolicyType(policy_type),
            policy_text=policy_text
        )
        
        # Stage results storage
        self.validation_result = None
        self.confidence = None
        self.confidence_percent = None
        self.match_result = None
        self.compliance_report = None
        self.improved_policy_result = None
        self.analyzer_service = None
        
        # Early exit flag
        self.should_exit = False
        self.exit_result = None
        
        # Error tracking
        self.critical_error = None
        self.error_type = None
        self.failed_stages = []


class StageExecutor:
    """
    Executes stages using OOP stage classes
    """
    
    def __init__(self, context: StageContext):
        self.context = context
        # Instantiate stage objects with context
        self.stages = [stage_class(context) for stage_class in STAGE_CLASSES]
        # We'll calculate total_stages dynamically as we execute
        # Start with max possible (all stages)
        self.total_stages = len(self.stages)
    
    def _calculate_total_stages(self) -> int:
        """
        Calculate how many stages will actually run
        This is called after stage 0 to get accurate count
        """
        count = 0
        for stage in self.stages:
            if stage.should_run():
                count += 1
        return count
    
    async def execute_all_stages(self) -> Dict[str, Any]:
        """
        Execute all stages in order
        """
        current_stage_num = 0
        
        # After stage 0, recalculate total based on actual stages that will run
        # This gives more accurate progress tracking
        recalculated_total = False
        
        for stage in self.stages:
            # Check if stage should run
            if not stage.should_run():
                app_logger.info(
                    f"⏭️ [Task {self.context.task.request.id}] "
                    f"Skipping {stage.name} (condition not met)"
                )
                continue
            
            current_stage_num += 1
            
            # Recalculate total after stage 0 (when we know which stages will run)
            if not recalculated_total and current_stage_num > 1:
                self.total_stages = self._calculate_total_stages()
                recalculated_total = True
                app_logger.debug(
                    f"📊 [Task {self.context.task.request.id}] "
                    f"Total stages that will run: {self.total_stages}"
                )
            
            # Update task state
            stage.update_progress(current_stage_num, self.total_stages)
            
            app_logger.info(
                f"▶ [{stage.__class__.__name__}] [Task {self.context.task.request.id}] "
                f"{stage.name}"
            )
            
            # Execute stage
            try:
                await stage.execute()
                
                # Check for early exit
                if self.context.should_exit:
                    return self.context.exit_result
                    
            except Exception as e:
                error_message = str(e)
                error_lower = error_message.lower()
                
                app_logger.error(
                    f"❌ [Task {self.context.task.request.id}] "
                    f"Stage {stage.name} failed: {error_message}"
                )
                
                # Track failed stage
                self.context.failed_stages.append({
                    'stage': stage.__class__.__name__,
                    'error': error_message,
                    'required': stage.required
                })
                
                # Classify error type
                if any(keyword in error_lower for keyword in ['quota', '429', 'rate limit', 'billing']):
                    self.context.error_type = 'quota_exceeded'
                    self.context.critical_error = f"تم تجاوز الحصة المسموحة: {error_message}"
                elif any(keyword in error_lower for keyword in ['timeout', 'timed out']):
                    self.context.error_type = 'timeout'
                    self.context.critical_error = f"انتهت مهلة الانتظار: {error_message}"
                elif any(keyword in error_lower for keyword in ['401', '403', 'unauthorized', 'forbidden', 'api key']):
                    self.context.error_type = 'authentication'
                    self.context.critical_error = f"خطأ في المصادقة: {error_message}"
                else:
                    self.context.error_type = 'unknown'
                    self.context.critical_error = error_message
                
                # Try graceful degradation for non-critical errors
                if stage.required:
                    # For required stages, try graceful degradation first
                    fallback_result = await graceful_degradation_service.get_cached_similar_result(
                        self.context.policy_text, self.context.policy_type
                    )
                    
                    if fallback_result:
                        app_logger.info(
                            f"✨ [Task {self.context.task.request.id}] "
                            f"Using graceful degradation fallback after {stage.name} failure"
                        )
                        return {
                            'success': True,
                            'from_cache': False,
                            'result': fallback_result
                        }
                    
                    # If required stage fails and no fallback, raise to fail the task
                    app_logger.error(
                        f"💥 [Task {self.context.task.request.id}] "
                        f"Required stage {stage.name} failed with no fallback - Task will fail"
                    )
                    raise
                else:
                    # For optional stages, log and continue
                    app_logger.warning(
                        f"⚠️ [Task {self.context.task.request.id}] "
                        f"Optional stage {stage.name} failed, continuing..."
                    )
        
        # Ensure progress reaches 100% by updating one final time
        self.context.task.update_state(
            state='PROGRESS',
            meta={
                'current': current_stage_num,
                'total': current_stage_num,  # Set total to current to show 100%
                'status': 'إنهاء التحليل...',
                'shop_name': self.context.shop_name
            }
        )
        
        # Build final result
        return await self._build_final_result()
    
    async def _build_final_result(self) -> Dict[str, Any]:
        """Build the final analysis result"""
        
        # Validate that we have critical data before building result
        if self.context.compliance_report is None:
            error_msg = self.context.critical_error or "فشل تحليل الامتثال - لا توجد بيانات التقرير"
            app_logger.error(
                f"💥 [Task {self.context.task.request.id}] "
                f"Cannot build result: {error_msg}"
            )
            raise Exception(
                f"فشل التحليل: {error_msg}. "
                f"المراحل الفاشلة: {', '.join([s['stage'] for s in self.context.failed_stages])}"
            )
        
        if self.context.match_result is None:
            error_msg = "فشل التحقق من مطابقة السياسة"
            app_logger.error(
                f"💥 [Task {self.context.task.request.id}] "
                f"Cannot build result: {error_msg}"
            )
            raise Exception(f"فشل التحليل: {error_msg}")
        
        # Build successful result
        result = AnalysisResponse(
            success=True,
            message="تم التحليل بنجاح",
            policy_match=self.context.match_result,
            compliance_report=self.context.compliance_report,
            improved_policy=self.context.improved_policy_result,
            shop_name=self.context.shop_name,
            shop_specialization=self.context.shop_specialization,
            policy_type=PolicyType(self.context.policy_type),
            analysis_timestamp=datetime.utcnow().isoformat()
        )
        
        result_dict = result.model_dump()
        result_dict['from_cache'] = False
        result_dict['task_id'] = self.context.task.request.id
        result_dict['timestamp'] = datetime.utcnow().isoformat()
        
        # Add warning if there were non-critical failures
        if self.context.failed_stages:
            warnings = [f"تحذير: فشلت المرحلة {s['stage']}" for s in self.context.failed_stages if not s['required']]
            if warnings:
                result_dict['warnings'] = warnings
                app_logger.warning(
                    f"⚠️ [Task {self.context.task.request.id}] "
                    f"Completed with warnings: {warnings}"
                )
        
        # Cache for idempotency
        if self.context.idempotency_key and result.success:
            await idempotency_service.store_result(self.context.idempotency_key, result_dict)
            app_logger.info(
                f"💾 [Task {self.context.task.request.id}] "
                f"Result cached for idempotency"
            )
        
        # Cache for graceful degradation
        if result.success:
            await graceful_degradation_service.cache_successful_result(
                self.context.policy_text,
                self.context.policy_type,
                result_dict
            )
            app_logger.info(
                f"💾 [Task {self.context.task.request.id}] "
                f"Result cached for graceful degradation"
            )
        
        app_logger.info(
            f"✅ [Task {self.context.task.request.id}] Analysis completed successfully - "
            f"Compliance: {self.context.compliance_report.overall_compliance_ratio}%"
        )
        
        return {
            'success': True,
            'from_cache': False,
            'result': result_dict
        }


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
    
    Uses OOP-based stage classes for easy management.
    Each stage is a separate class inheriting from BaseStage.
    To add/remove stages, modify the STAGE_CLASSES list.
    
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
                'total': len(STAGE_CLASSES),
                'status': 'بدء التحليل...',
                'shop_name': shop_name
            }
        )
        
        # Initialize Redis connections
        await idempotency_service.connect()
        await graceful_degradation_service.connect()
        
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
        
        # Create stage context
        context = StageContext(
            task_instance=self,
            shop_name=shop_name,
            shop_specialization=shop_specialization,
            policy_type=policy_type,
            policy_text=policy_text,
            idempotency_key=idempotency_key
        )
        
        # Execute all stages using StageExecutor
        executor = StageExecutor(context)
        result = await executor.execute_all_stages()
        
        return result
        
    except SoftTimeLimitExceeded:
        error_msg = 'تجاوز الوقت المسموح للتحليل'
        app_logger.error(f"⏱️ [Task {self.request.id}] Soft time limit exceeded")
        # Raise exception to mark task as FAILURE in Celery
        raise Exception(f"[timeout] {error_msg}")
        
    except Exception as e:
        error_message = str(e)
        error_lower = error_message.lower()
        
        app_logger.error(f"❌ [Task {self.request.id}] Error: {error_message}")
        
        # Classify error for better handling
        error_type = 'unknown'
        if any(keyword in error_lower for keyword in ['quota', '429', 'rate limit', 'billing']):
            error_type = 'quota_exceeded'
        elif any(keyword in error_lower for keyword in ['timeout', 'timed out']):
            error_type = 'timeout'
        elif any(keyword in error_lower for keyword in ['401', '403', 'unauthorized', 'forbidden']):
            error_type = 'authentication'
        
        # Don't retry for quota/authentication errors - they won't fix themselves
        should_retry = error_type not in ['quota_exceeded', 'authentication']
        
        if should_retry and self.request.retries < self.max_retries:
            app_logger.info(f"🔄 [Task {self.request.id}] Retrying... ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        # Raise exception to mark task as FAILED in Celery
        # This ensures the task status is 'FAILURE' not 'SUCCESS'
        app_logger.error(
            f"💥 [Task {self.request.id}] Task failed permanently - "
            f"Error type: {error_type}, Message: {error_message}"
        )
        raise Exception(f"[{error_type}] {error_message}")
    
    finally:
        # Cleanup
        await idempotency_service.disconnect()
        await graceful_degradation_service.disconnect()


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