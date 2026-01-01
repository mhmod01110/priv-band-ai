"""
Base Stage Class
All stages inherit from this class
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.logger import app_logger


class BaseStage(ABC):
    """
    Base class for all analysis stages
    
    Each stage must implement:
    - name: Display name
    - status_message: User-facing status message
    - required: Whether stage must run
    - execute(): The main execution logic
    - should_run(): Conditional check (optional)
    """
    
    def __init__(self, context):
        """
        Initialize stage with context
        
        Args:
            context: StageContext object containing task data
        """
        self.context = context
        self.logger = app_logger
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Stage display name"""
        pass
    
    @property
    @abstractmethod
    def status_message(self) -> str:
        """User-facing status message"""
        pass
    
    @property
    @abstractmethod
    def required(self) -> bool:
        """Whether this stage is required"""
        pass
    
    @abstractmethod
    async def execute(self) -> None:
        """
        Execute the stage logic
        
        Raises:
            Exception: If stage fails and should stop execution
        """
        pass
    
    def should_run(self) -> bool:
        """
        Check if stage should run (conditional logic)
        
        Returns:
            True if stage should run, False otherwise
        """
        return True  # Default: always run
    
    def update_progress(self, current: int, total: int, status: str = None):
        """
        Update task progress
        
        Args:
            current: Current stage number
            total: Total stages
            status: Optional custom status message
        """
        self.context.task.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'status': status or self.status_message,
                'shop_name': self.context.shop_name
            }
        )
    
    def log_info(self, message: str):
        """Log info message with task ID"""
        task_id = self.context.task.request.id
        self.logger.info(f"[{self.name}] [Task {task_id}] {message}")
    
    def log_error(self, message: str):
        """Log error message with task ID"""
        task_id = self.context.task.request.id
        self.logger.error(f"[{self.name}] [Task {task_id}] {message}")
    
    def log_warning(self, message: str):
        """Log warning message with task ID"""
        task_id = self.context.task.request.id
        self.logger.warning(f"[{self.name}] [Task {task_id}] {message}")

