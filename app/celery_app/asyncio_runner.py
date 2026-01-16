# app/celery_app/asyncio_runner.py
import asyncio
import threading
from typing import Optional, Any, Coroutine

_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None


def start_loop_thread() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop and _loop.is_running():
        return _loop

    ready = threading.Event()

    def _run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        ready.set()
        _loop.run_forever()

    _thread = threading.Thread(target=_run, name="celery-asyncio-loop", daemon=True)
    _thread.start()
    ready.wait()
    return _loop


def stop_loop_thread():
    global _loop
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(_loop.stop)
    _loop = None


def run_async(coro: Coroutine[Any, Any, Any], timeout: Optional[float] = None) -> Any:
    """
    Run an async coroutine on the dedicated loop thread and wait for result.
    Works fine under gevent because monkey.patch_all patches thread primitives.
    """
    loop = start_loop_thread()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=timeout)
