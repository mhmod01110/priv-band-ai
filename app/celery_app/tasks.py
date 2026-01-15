"""
Celery Task Definitions with Pre-Stage Validation
All long-running analysis tasks with comprehensive input validation
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

from app.utils.validators import validate_input_before_processing


# Import safeguards for pre-validation
from app.safeguards import (
    input_sanitizer,
    content_filter,
    openai_safeguard
)

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
    Base Task class optimized for gevent pool
    """
    _event_loop = None
    
    @classmethod
    def get_event_loop(cls):
        """
        احصل على event loop مشترك بدل إنشاء واحد جديد لكل task
        ده بيحسن الأداء جداً
        """
        if cls._event_loop is None or cls._event_loop.is_closed():
            cls._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(cls._event_loop)
        return cls._event_loop
    
    def __call__(self, *args, **kwargs):
        """
        تنفيذ الـ task باستخدام event loop مشترك
        """
        loop = self.get_event_loop()
        try:
            return loop.run_until_complete(self.run(*args, **kwargs))
        except Exception as e:
            # تسجيل الخطأ
            from app.logger import app_logger
            app_logger.error(f"Task {self.name} failed: {str(e)}")
            raise
    
    async def run(self, *args, **kwargs) -> Any:
        """
        Override this method in subclasses
        """
        raise NotImplementedError("Subclasses must implement run()")


class StageContext:
    """Context object to pass data between stages"""
    def __init__(self, task_instance, shop_name: str, shop_specialization: str, 
                 policy_type: str, policy_text: str, idempotency_key: str = None,
                 force_refresh: bool = False):
        self.task = task_instance
        self.shop_name = shop_name
        self.shop_specialization = shop_specialization
        self.policy_type = policy_type
        self.policy_text = policy_text
        self.idempotency_key = idempotency_key
        self.force_refresh = force_refresh  # Flag to skip graceful degradation
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
    """Executes stages using OOP stage classes"""
    
    def __init__(self, context: StageContext):
        self.context = context
        self.stages = [stage_class(context) for stage_class in STAGE_CLASSES]
        self.total_stages = len(self.stages)
    
    def _calculate_total_stages(self) -> int:
        """Calculate how many stages will actually run"""
        count = 0
        for stage in self.stages:
            if stage.should_run():
                count += 1
        return count
    
    async def execute_all_stages(self) -> Dict[str, Any]:
        """Execute all stages in order"""
        current_stage_num = 0
        recalculated_total = False
        
        for stage in self.stages:
            if not stage.should_run():
                app_logger.info(
                    f"⏭️ [Task {self.context.task.request.id}] "
                    f"Skipping {stage.name} (condition not met)"
                )
                continue
            
            current_stage_num += 1
            
            if not recalculated_total and current_stage_num > 1:
                self.total_stages = self._calculate_total_stages()
                recalculated_total = True
                app_logger.debug(
                    f"📊 [Task {self.context.task.request.id}] "
                    f"Total stages that will run: {self.total_stages}"
                )
            
            stage.update_progress(current_stage_num, self.total_stages)
            
            app_logger.info(
                f"▶ [{stage.__class__.__name__}] [Task {self.context.task.request.id}] "
                f"{stage.name}"
            )
            
            try:
                await stage.execute()
                
                if self.context.should_exit:
                    exit_result = self.context.exit_result
                    
                    # Check if the exit result is actually a failure
                    if exit_result and isinstance(exit_result, dict):
                        nested_result = exit_result.get('result', {})
                        if isinstance(nested_result, dict) and not nested_result.get('success', True):
                            # This is a failure result (like policy mismatch), don't cache it
                            app_logger.warning(
                                f"⚠️ [Task {self.context.task.request.id}] "
                                f"Early exit with failure result - will not cache"
                            )
                            # Don't cache failure results
                            return exit_result
                    
                    # For successful early exits (if any), cache normally
                    if self.context.idempotency_key and exit_result:
                        nested_result = exit_result.get('result', {})
                        if isinstance(nested_result, dict) and nested_result.get('success', False):
                            app_logger.info(
                                f"💾 [Task {self.context.task.request.id}] "
                                f"Attempting to cache early exit result..."
                            )
                            cache_success = await idempotency_service.store_result(
                                self.context.idempotency_key, 
                                nested_result
                            )
                            if cache_success:
                                app_logger.info(
                                    f"✅ [Task {self.context.task.request.id}] "
                                    f"Early exit result cached successfully"
                                )
                            else:
                                app_logger.error(
                                    f"❌ [Task {self.context.task.request.id}] "
                                    f"Failed to cache early exit result"
                                )
                    
                    return exit_result
                    
            except Exception as e:
                error_message = str(e)
                error_lower = error_message.lower()
                
                app_logger.error(
                    f"❌ [Task {self.context.task.request.id}] "
                    f"Stage {stage.name} failed: {error_message}"
                )
                
                self.context.failed_stages.append({
                    'stage': stage.__class__.__name__,
                    'stage_number': current_stage_num,
                    'stage_name': stage.name,
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
                    # For quota/auth errors, don't try fallback - fail immediately
                    if self.context.error_type in ['quota_exceeded', 'authentication']:
                        app_logger.error(
                            f"💥 [Task {self.context.task.request.id}] "
                            f"Critical error {self.context.error_type} - no fallback attempted"
                        )
                        raise
                    
                    # If force_refresh is true, don't use cached fallback - user wants fresh analysis
                    if self.context.force_refresh:
                        app_logger.info(
                            f"🔄 [Task {self.context.task.request.id}] "
                            f"Force refresh enabled - skipping graceful degradation fallback"
                        )
                        raise
                    
                    fallback_result = await graceful_degradation_service.get_cached_similar_result(
                        self.context.policy_text, self.context.policy_type
                    )
                    
                    if fallback_result:
                        # Check if fallback is actually successful
                        if fallback_result.get('success', False):
                            app_logger.info(
                                f"✨ [Task {self.context.task.request.id}] "
                                f"Using graceful degradation fallback after {stage.name} failure"
                            )
                            return {
                                'success': True,
                                'from_cache': False,
                                'result': fallback_result,
                                'used_fallback': True
                            }
                        else:
                            app_logger.warning(
                                f"⚠️ [Task {self.context.task.request.id}] "
                                f"Fallback result was also a failure - will not use it"
                            )
                    
                    app_logger.error(
                        f"💥 [Task {self.context.task.request.id}] "
                        f"Required stage {stage.name} failed with no fallback - Task will fail"
                    )
                    raise
                else:
                    app_logger.warning(
                        f"⚠️ [Task {self.context.task.request.id}] "
                        f"Optional stage {stage.name} failed, continuing..."
                    )
        
        # Ensure progress reaches 100%
        self.context.task.update_state(
            state='PROGRESS',
            meta={
                'current': current_stage_num,
                'total': current_stage_num,
                'status': 'إنهاء التحليل...',
                'shop_name': self.context.shop_name
            }
        )
        
        return await self._build_final_result()
    
    async def _build_final_result(self) -> Dict[str, Any]:
        """Build the final analysis result"""
        
        if self.context.compliance_report is None:
            error_msg = self.context.critical_error or "فشل تحليل الامتثال - لا توجد بيانات التقرير"
            app_logger.error(
                f"💥 [Task {self.context.task.request.id}] "
                f"Cannot build result: {error_msg}"
            )
            raise Exception(
                f"فشل التحليل: {error_msg}. "
                f"المراحل الفاشلة: {', '.join([s['stage_name'] for s in self.context.failed_stages])}"
            )
        
        if self.context.match_result is None:
            error_msg = "فشل التحقق من مطابقة السياسة"
            app_logger.error(
                f"💥 [Task {self.context.task.request.id}] "
                f"Cannot build result: {error_msg}"
            )
            raise Exception(f"فشل التحليل: {error_msg}")
        
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
        
        if self.context.failed_stages:
            warnings = [f"تحذير: فشلت المرحلة {s['stage_name']}" for s in self.context.failed_stages if not s['required']]
            if warnings:
                result_dict['warnings'] = warnings
                app_logger.warning(
                    f"⚠️ [Task {self.context.task.request.id}] "
                    f"Completed with warnings: {warnings}"
                )
        
        # Only cache truly successful results (success=True AND has compliance_report)
        should_cache = (
            result.success and 
            self.context.compliance_report is not None and
            self.context.compliance_report.overall_compliance_ratio is not None
        )
        
        # 🔍 DEBUG LOGGING
        app_logger.info(f"🔍 [Task {self.context.task.request.id}] Cache decision analysis:")
        app_logger.info(f"  - should_cache: {should_cache}")
        app_logger.info(f"  - idempotency_key exists: {bool(self.context.idempotency_key)}")
        app_logger.info(f"  - result.success: {result.success}")
        app_logger.info(f"  - has compliance_report: {self.context.compliance_report is not None}")
        if self.context.compliance_report:
            app_logger.info(f"  - compliance_ratio: {self.context.compliance_report.overall_compliance_ratio}")
        
        if self.context.idempotency_key and should_cache:
            app_logger.info(
                f"💾 [Task {self.context.task.request.id}] "
                f"Attempting to cache result with key: {self.context.idempotency_key[:30]}..."
            )
            
            cache_success = await idempotency_service.store_result(
                self.context.idempotency_key, 
                result_dict
            )
            
            if cache_success:
                app_logger.info(
                    f"✅ [Task {self.context.task.request.id}] "
                    f"Result cached successfully for idempotency"
                )
            else:
                app_logger.error(
                    f"❌ [Task {self.context.task.request.id}] "
                    f"Failed to cache result for idempotency"
                )
        elif self.context.idempotency_key and not should_cache:
            app_logger.info(
                f"⏭️ [Task {self.context.task.request.id}] "
                f"Result NOT cached (success={result.success}, has_report={self.context.compliance_report is not None})"
            )
        elif not self.context.idempotency_key:
            app_logger.warning(
                f"⚠️ [Task {self.context.task.request.id}] "
                f"No idempotency_key provided - cannot cache"
            )
        
        # Cache for graceful degradation
        if should_cache:
            app_logger.info(
                f"💾 [Task {self.context.task.request.id}] "
                f"Attempting to cache for graceful degradation..."
            )
            
            degradation_cache_success = await graceful_degradation_service.cache_successful_result(
                self.context.policy_text,
                self.context.policy_type,
                result_dict
            )
            
            if degradation_cache_success:
                app_logger.info(
                    f"✅ [Task {self.context.task.request.id}] "
                    f"Result cached for graceful degradation"
                )
            else:
                app_logger.error(
                    f"❌ [Task {self.context.task.request.id}] "
                    f"Failed to cache for graceful degradation"
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
    soft_time_limit=540,
    time_limit=600
)
async def analyze_policy_task(
    self,
    shop_name: str,
    shop_specialization: str,
    policy_type: str,
    policy_text: str,
    idempotency_key: str = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Main Policy Analysis Task with Pre-Stage Validation
    """
    app_logger.info(
        f"🚀 [Celery Task {self.request.id}] Starting analysis for: {shop_name} (force_refresh={force_refresh})"
    )
    
    try:
        # ===== PRE-STAGE VALIDATION =====
        is_valid, validation_error = validate_input_before_processing(
            shop_name, shop_specialization, policy_text, self.request.id
        )
        
        if not is_valid:
            app_logger.error(
                f"🚫 [Task {self.request.id}] Pre-validation failed: "
                f"{validation_error['error_category']}"
            )
            # Return structured error immediately - don't start stages
            return {
                'success': False,
                'from_cache': False,
                'result': validation_error
            }
        
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
        
        # ✅ MongoDB is already connected via worker_process_init signal
        # ❌ REMOVED: await idempotency_service.connect()
        # ❌ REMOVED: await graceful_degradation_service.connect()
        
        app_logger.info(
            f"📊 [Task {self.request.id}] MongoDB connection status: "
            f"{await idempotency_service.mongodb.is_connected()}"
        )
        
        # Check cache first (skip if force_refresh)
        if idempotency_key and not force_refresh:
            app_logger.info(
                f"🔍 [Task {self.request.id}] Checking cache with key: {idempotency_key[:30]}..."
            )
            cached_result = await idempotency_service.get_cached_result(idempotency_key)
            if cached_result:
                app_logger.info(f"✅ [Task {self.request.id}] Cache HIT - Returning cached result")
                return {
                    'success': True,
                    'from_cache': True,
                    'result': cached_result
                }
            app_logger.info(f"ℹ️ [Task {self.request.id}] Cache MISS - Will execute analysis")
        elif force_refresh:
            app_logger.info(f"🔄 [Task {self.request.id}] Force refresh - skipping cache check")
        elif not idempotency_key:
            app_logger.warning(f"⚠️ [Task {self.request.id}] No idempotency_key provided")
        
        # Create stage context
        context = StageContext(
            task_instance=self,
            shop_name=shop_name,
            shop_specialization=shop_specialization,
            policy_type=policy_type,
            policy_text=policy_text,
            idempotency_key=idempotency_key,
            force_refresh=force_refresh
        )
        
        # Execute all stages
        executor = StageExecutor(context)
        result = await executor.execute_all_stages()
        
        return result
        
    except SoftTimeLimitExceeded:
        error_msg = 'تجاوز الوقت المسموح للتحليل'
        app_logger.error(f"⏱️ [Task {self.request.id}] Soft time limit exceeded")
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
        
        # Don't retry for quota/authentication errors
        should_retry = error_type not in ['quota_exceeded', 'authentication']
        
        if should_retry and self.request.retries < self.max_retries:
            app_logger.info(f"🔄 [Task {self.request.id}] Retrying... ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        app_logger.error(
            f"💥 [Task {self.request.id}] Task failed permanently - "
            f"Error type: {error_type}, Message: {error_message}"
        )
        raise Exception(f"[{error_type}] {error_message}")
    
    # ❌ REMOVED: finally block with disconnect
    # MongoDB connection persists across tasks in the worker process


@celery_app.task(name='app.celery_app.tasks.cleanup_old_results')
def cleanup_old_results():
    """Periodic task to cleanup old cached results"""
    app_logger.info("🧹 Running cleanup of old results...")
    
    try:
        # Note: Cleanup is handled automatically by MongoDB TTL indexes
        # This task is kept for manual cleanup if needed
        app_logger.info("✅ Cleanup completed (handled by MongoDB TTL)")
        return {'status': 'success', 'message': 'Cleanup completed'}
        
    except Exception as e:
        app_logger.error(f"❌ Cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='app.celery_app.tasks.health_check')
def health_check():
    """Health check task for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker_id': health_check.request.id
    }