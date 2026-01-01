"""
Stage 0: Policy Validation (No AI)
Rule-based validation without AI
"""
from datetime import datetime
from app.celery_app.stages.base import BaseStage
from app.services.graceful_degradation import graceful_degradation_service
from app.services.analyzer_service import AnalyzerService
from app.utils.policy_validator import enhanced_policy_validation
from app.config import get_settings

settings = get_settings()


class Stage0Validation(BaseStage):
    """Stage 0: Policy Validation using rule-based validator (no AI)"""
    
    @property
    def name(self) -> str:
        return 'Policy Validation (No AI)'
    
    @property
    def status_message(self) -> str:
        return 'التحقق الأولي من السياسة (بدون ذكاء اصطناعي)...'
    
    @property
    def required(self) -> bool:
        return True
    
    def should_run(self) -> bool:
        """Always runs (no condition)"""
        return True
    
    async def execute(self) -> None:
        """Execute policy validation"""
        should_use_ai, validation_result = enhanced_policy_validation(
            policy_type=self.context.policy_type,
            policy_text=self.context.policy_text
        )
        
        self.context.validation_result = validation_result
        self.context.confidence = validation_result.get('confidence', 0.5)
        self.context.confidence_percent = self.context.confidence * 100
        
        self.log_info(
            f"Stage 0 Result - Confidence: {self.context.confidence_percent:.1f}%"
        )
        
        # Check if policy is clearly mismatched
        if validation_result.get('is_matched') is False and self.context.confidence < 0.3:
            self.log_warning(
                f"Policy mismatch detected - Confidence: {self.context.confidence_percent:.1f}%"
            )
            
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
            
            # Return early rejection
            result_dict = {
                'success': False,
                'message': f"نوع السياسة المحدد لا يطابق محتوى النص. {validation_result.get('reason', '')}",
                'policy_match': {
                    'is_matched': False,
                    'confidence': self.context.confidence_percent,
                    'reason': validation_result.get('reason', 'عدم تطابق واضح'),
                    'method': 'rule_based_stage_0'
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
        
        # Initialize analyzer service for later stages
        self.context.analyzer_service = AnalyzerService(provider=settings.ai_provider)

