"""
Stage 5: Finalization
Marks completion of analysis
"""
from app.celery_app.stages.base import BaseStage


class Stage5Finalization(BaseStage):
    """Stage 5: Finalization"""
    
    @property
    def name(self) -> str:
        return 'Finalization'
    
    @property
    def status_message(self) -> str:
        return 'إنهاء التحليل...'
    
    @property
    def required(self) -> bool:
        return True
    
    def should_run(self) -> bool:
        """Always runs at the end"""
        return True
    
    async def execute(self) -> None:
        """Execute finalization (no-op, actual finalization happens in executor)"""
        # This stage just marks completion
        # Actual finalization happens in StageExecutor._build_final_result()
        pass

