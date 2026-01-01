"""
Stage 4: Policy Regeneration (Conditional)
Only runs if compliance < 95%
"""
from app.celery_app.stages.base import BaseStage


class Stage4Regeneration(BaseStage):
    """Stage 4: Policy Regeneration (conditional)"""
    
    @property
    def name(self) -> str:
        return 'Policy Regeneration'
    
    @property
    def status_message(self) -> str:
        return 'إعادة كتابة السياسة المحسّنة...'
    
    @property
    def required(self) -> bool:
        return False  # Optional - only if compliance < 95%
    
    def should_run(self) -> bool:
        """Check if policy regeneration should run (compliance < 95%)"""
        if self.context.compliance_report is None:
            return False
        return self.context.compliance_report.overall_compliance_ratio < 95
    
    async def execute(self) -> None:
        """Execute policy regeneration"""
        try:
            self.context.improved_policy_result = await self.context.analyzer_service._regenerate_policy(
                self.context.shop_name,
                self.context.shop_specialization,
                self.context.policy_type,
                self.context.policy_text,
                self.context.compliance_report
            )
        except Exception as e:
            self.log_error(f"Policy regeneration failed: {str(e)}")
            # Continue without improved policy (optional stage)

