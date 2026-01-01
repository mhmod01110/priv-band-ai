"""
Stage 1: Check Policy with AI (Conditional)
Only runs if uncertainty is in 30-70% range
"""
from app.celery_app.stages.base import BaseStage
from app.models import PolicyMatchResult


class Stage1AICheck(BaseStage):
    """Stage 1: Check Policy with AI (conditional)"""
    
    @property
    def name(self) -> str:
        return 'Check Policy with AI'
    
    @property
    def status_message(self) -> str:
        return 'التحقق من مطابقة السياسة باستخدام الذكاء الاصطناعي...'
    
    @property
    def required(self) -> bool:
        return False  # Optional - only runs if condition met
    
    def should_run(self) -> bool:
        """Check if AI Stage 1 should run (30-70% uncertainty)"""
        if self.context.confidence is None:
            return False
        return 0.30 <= self.context.confidence <= 0.70
    
    async def execute(self) -> None:
        """Execute AI policy match check"""
        try:
            match_result = await self.context.analyzer_service._check_policy_match(
                self.context.policy_type,
                self.context.policy_text
            )
            
            if not match_result.is_matched:
                self.log_warning("AI confirmed policy mismatch")
                # Store result for Stage 2 (Cache retrieval) to handle
                self.context.match_result = match_result
                return
            
            self.context.match_result = match_result
            self.log_info(
                f"AI confirmed policy match - Confidence: {match_result.confidence}%"
            )
            
        except Exception as e:
            self.log_error(f"AI Stage 1 failed: {str(e)} - Falling back to rule-based result")
            # Fallback to rule-based result
            self.context.match_result = PolicyMatchResult(
                is_matched=self.context.validation_result.get('is_matched', True),
                confidence=self.context.confidence_percent,
                reason=self.context.validation_result.get('reason', 'تم التحقق باستخدام القواعد المحلية')
            )

