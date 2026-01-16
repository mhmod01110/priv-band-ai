"""
Celery Worker Signals
Initialize connections when worker starts (gevent-safe)
"""
from celery.signals import worker_init, worker_shutdown
from app.logger import app_logger
from app.services.mongodb_client import mongodb_client

from app.celery_app.asyncio_runner import start_loop_thread, stop_loop_thread, run_async


@worker_init.connect
def init_worker(**kwargs):
    """
    Initialize resources once when worker starts.
    gevent pool => no process init signal => use worker_init.
    """
    app_logger.info("🔄 Initializing Celery worker (gevent-safe)...")

    try:
        # start dedicated asyncio loop thread
        start_loop_thread()

        # Connect MongoDB on that loop
        run_async(mongodb_client.connect())
        app_logger.info("✅ MongoDB connected (async loop thread)")

        app_logger.info("✅ Worker initialization complete")
    except Exception as e:
        app_logger.error(f"❌ Failed to initialize worker: {str(e)}")
        raise


@worker_shutdown.connect
def shutdown_worker(**kwargs):
    """Cleanup connections when worker shuts down"""
    app_logger.info("🛑 Shutting down Celery worker connections...")

    try:
        # Disconnect MongoDB on the same loop
        run_async(mongodb_client.disconnect())
        stop_loop_thread()
        app_logger.info("✅ Worker shutdown complete")
    except Exception as e:
        app_logger.error(f"⚠️ Error during worker shutdown: {str(e)}")
