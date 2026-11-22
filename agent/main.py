"""
FixOps - Agent FastAPI entry point (Personne 1)

Place this file at: agent/main.py

Starts the Agent API and exactly one monitoring loop in the same process.
Run Uvicorn with ONE worker:
    uvicorn agent.main:app --host 0.0.0.0 --port 8001 --workers 1

Do not start monitoring.py separately when using this entry point.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent.monitoring import Monitoring, POLL_SECONDS
from agent.reporter import pending_count, send_incident

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOCK_PATH = Path(
    os.getenv("AGENT_MONITOR_LOCK", "/tmp/fixops-agent-monitoring.lock")
)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fixops.agent")

_monitor_thread: threading.Thread | None = None
_lock_file = None
_monitoring_started = False


def _acquire_monitor_lock():
    """
    Linux process lock: prevents a second Agent process from starting another
    monitoring loop on the same VM.
    """
    import fcntl

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError(
            "Another FixOps Agent process already owns the monitoring lock. "
            "Stop the duplicate process/service before starting this one."
        ) from exc
    return lock_file


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    global _monitor_thread, _lock_file, _monitoring_started

    # Uvicorn's multiple workers would each execute this lifespan.
    workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    if workers > 1:
        raise RuntimeError(
            "FixOps Agent must run with one Uvicorn worker "
            "(use --workers 1) to avoid duplicate monitoring loops."
        )

    _lock_file = _acquire_monitor_lock()

    monitor = Monitoring(
        report_callback=send_incident,
        poll_seconds=POLL_SECONDS,
    )
    _monitor_thread = threading.Thread(
        target=monitor.run_forever,
        name="fixops-monitoring",
        daemon=True,
    )
    _monitor_thread.start()
    _monitoring_started = True
    logger.info("Agent API started; one monitoring loop active")

    try:
        yield
    finally:
        _monitoring_started = False
        # run_forever() is a daemon loop. It exits when this process shuts down.
        if _lock_file is not None:
            try:
                import fcntl
                fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
                _lock_file.close()
            finally:
                _lock_file = None
        logger.info("Agent API shutdown")


app = FastAPI(
    title="FixOps Agent API",
    version="1.0.0",
    description="Local Agent API and monitoring for the FixOps VM.",
    lifespan=lifespan,
)


@app.get("/agent/health")
async def agent_health():
    """Health endpoint used by the Windows Backend/operator to verify the Agent."""
    thread_alive = bool(_monitor_thread and _monitor_thread.is_alive())
    is_running = _monitoring_started and thread_alive
    return JSONResponse(
        status_code=200 if is_running else 503,
        content={
            "status": "ok" if is_running else "starting_or_stopped",
            "service": "fixops-agent",
            "monitoring": "running" if is_running else "not_running",
            "poll_seconds": POLL_SECONDS,
            "pending_incidents": pending_count(),
        },
    )


@app.get("/")
async def root():
    return {
        "service": "FixOps Agent",
        "health": "/agent/health",
        "api_docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.main:app",
        host="0.0.0.0",
        port=int(os.getenv("AGENT_PORT", "8001")),
        workers=1,
        reload=False,
    )
