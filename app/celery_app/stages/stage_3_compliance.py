"""
Stage 3: Compliance Analysis
Required stage - analyzes legal compliance
"""
from app.celery_app.stages.base import BaseStage
from app.models import PolicyMatchResult


class Stage3Compliance(BaseStage):
    """Stage 3: Compliance Analysis"""
    
    @property
    def name(self) -> str:
        return 'Compliance Analysis'
    
    @property
    def status_message(self) -> str:
        return 'تحليل الامتثال القانوني...'
    
    @property
    def required(self) -> bool:
        return True
    
    def should_run(self) -> bool:
        """Always runs after stage 0/1/2"""
        return True
    
    async def execute(self) -> None:
        """Execute compliance analysis"""
        # This is a required stage - if it fails, the task should fail
        try:
            self.context.compliance_report = await self.context.analyzer_service._analyze_compliance(
                self.context.shop_name,
                self.context.shop_specialization,
                self.context.policy_type,
                self.context.policy_text
            )
            
            # Validate that we got a compliance report
            if self.context.compliance_report is None:
                raise Exception("فشل تحليل الامتثال - لم يتم إرجاع تقرير")
                
        except Exception as e:
            # Re-raise to be caught by executor error handler
            raise
        
        # Set match_result if not already set (in case stage 1 was skipped)
        if self.context.match_result is None:
            self.context.match_result = PolicyMatchResult(
                is_matched=self.context.validation_result.get('is_matched', True),
                confidence=self.context.confidence_percent,
                reason=self.context.validation_result.get('reason', 'تم التحقق باستخدام القواعد المحلية')
            )

