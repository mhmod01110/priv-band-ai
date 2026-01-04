"""
Celery Worker Signals
Initialize connections when worker starts
"""
from celery.signals import worker_process_init, worker_process_shutdown
from app.logger import app_logger
from app.services.idempotency_service import idempotency_service
from app.services.graceful_degradation import graceful_degradation_service
from app.services.mongodb_client import mongodb_client
import asyncio


@worker_process_init.connect
def init_worker(**kwargs):
    """
    Initialize MongoDB connections when Celery worker starts
    This runs once per worker process
    """
    app_logger.info("🔄 Initializing Celery worker connections...")
    
    try:
        # Create new event loop for this worker process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Connect MongoDB
        loop.run_until_complete(mongodb_client.connect())
        app_logger.info("✅ MongoDB connected in worker process")
        
        # Services will reuse the same mongodb_client instance
        app_logger.info("✅ Worker initialization complete")
        
    except Exception as e:
        app_logger.error(f"❌ Failed to initialize worker: {str(e)}")
        raise


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """
    Cleanup connections when worker shuts down
    """
    app_logger.info("🛑 Shutting down Celery worker connections...")
    
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(mongodb_client.disconnect())
        app_logger.info("✅ Worker shutdown complete")
    except Exception as e:
        app_logger.error(f"⚠️ Error during worker shutdown: {str(e)}")