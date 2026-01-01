"""
Stage 2: Cache Retrieval (Conditional)
Only runs if Stage 1 detected a mismatch
"""
from datetime import datetime
from app.celery_app.stages.base import BaseStage
from app.services.graceful_degradation import graceful_degradation_service


class Stage2CacheRetrieval(BaseStage):
    """Stage 2: Cache Retrieval (conditional)"""
    
    @property
    def name(self) -> str:
        return 'Cache Retrieval'
    
    @property
    def status_message(self) -> str:
        return 'البحث في الذاكرة المؤقتة...'
    
    @property
    def required(self) -> bool:
        return False  # Optional - only runs if condition met
    
    def should_run(self) -> bool:
        """Check if cache retrieval should run (if Stage 1 detected mismatch)"""
        # Run if match_result exists and indicates mismatch
        if self.context.match_result is None:
            return False
        return not self.context.match_result.is_matched
    
    async def execute(self) -> None:
        """Execute cache retrieval for graceful degradation"""
        # Only runs if Stage 1 detected a mismatch
        if self.context.match_result and not self.context.match_result.is_matched:
            try:
                # Try graceful degradation
                fallback_result = await graceful_degradation_service.get_cached_similar_result(
                    self.context.policy_text, self.context.policy_type
                )
                
                if fallback_result:
                    self.log_info("Using graceful degradation fallback")
                    self.context.should_exit = True
                    self.context.exit_result = {
                        'success': True,
                        'from_cache': False,
                        'result': fallback_result
                    }
                    return
                
                # If no cache found, prepare rejection result
                result_dict = {
                    'success': False,
                    'message': f"نوع السياسة المحدد لا يطابق محتوى النص. {self.context.match_result.reason}",
                    'policy_match': {
                        'is_matched': False,
                        'confidence': self.context.match_result.confidence,
                        'reason': self.context.match_result.reason,
                        'method': 'ai_stage_1'
                    },
                    'compliance_report': None,
                    'shop_name': self.context.shop_name,
                    'shop_specialization': self.context.shop_specialization,
                    'policy_type': self.context.policy_type,
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'from_cache': False,
                    'task_id': self.context.task.request.id
                }
                
                self.context.should_exit = True
                self.context.exit_result = {
                    'success': True,
                    'from_cache': False,
                    'result': result_dict
                }
                return
                
            except Exception as e:
                self.log_error(f"Cache retrieval failed: {str(e)}")
                # Continue - let the pipeline handle the mismatch

