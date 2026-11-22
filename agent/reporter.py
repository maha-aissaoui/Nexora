"""
FixOps - Incident reporter (Personne 1)

Place this file at: agent/reporter.py

Sends monitoring events to the central Windows Backend:
POST {CENTRAL_API_URL}/api/incidents

If the Backend is unavailable, the event is persisted in a local JSONL outbox.
A failed delivery raises IncidentDeliveryError so monitoring.py does NOT mark
the incident as transmitted. The next monitoring cycle retries delivery.

Environment variables:
    CENTRAL_API_URL       Example: http://192.168.56.1:8000
    AGENT_API_TOKEN       Bearer token shared with the central Backend
    HOST_ID               Optional; defaults to the machine hostname
    AGENT_OUTBOX_PATH     Optional; defaults to ~/.local/state/fixops-agent/outbox.jsonl
    REPORTER_TIMEOUT      Optional; defaults to 5 seconds
    REPORTER_RETRIES      Optional; defaults to 3 attempts
"""

from __future__ import annotations

import json
import logging
import os
import socket
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("fixops.reporter")

CENTRAL_API_URL = os.getenv("CENTRAL_API_URL", "http://192.168.56.1:8000").rstrip("/")
AGENT_API_TOKEN = os.getenv("AGENT_API_TOKEN", "").strip()
HOST_ID = os.getenv("HOST_ID", socket.gethostname())
OUTBOX_PATH = Path(
    os.getenv(
        "AGENT_OUTBOX_PATH",
        str(Path.home() / ".local/state/fixops-agent/outbox.jsonl"),
    )
).expanduser()
REQUEST_TIMEOUT = max(1, float(os.getenv("REPORTER_TIMEOUT", "5")))
MAX_ATTEMPTS = max(1, int(os.getenv("REPORTER_RETRIES", "3")))

_outbox_lock = threading.Lock()


class IncidentDeliveryError(RuntimeError):
    """Raised when an incident has not been confirmed by the central Backend."""


def _complete_event(event: dict[str, Any]) -> dict[str, Any]:
    """Copy and complete the incident without modifying monitoring's dictionary."""
    completed = dict(event)
    completed.setdefault("source", "nexora-agent")
    completed.setdefault("host_id", HOST_ID)
    completed.setdefault("observed_at", datetime.now(timezone.utc).isoformat())

    required = ("host_id", "service", "type")
    missing = [field for field in required if not completed.get(field)]
    if missing:
        raise ValueError(f"Incident is missing required field(s): {', '.join(missing)}")

    # The key remains identical across monitoring cycles for the same open incident.
    completed.setdefault(
        "event_key",
        f"{completed['host_id']}:{completed['service']}:{completed['type']}",
    )
    completed.setdefault("observed_status", "unknown")
    completed.setdefault("details", {})
    return completed


def _headers() -> dict[str, str]:
    if not AGENT_API_TOKEN:
        raise IncidentDeliveryError(
            "AGENT_API_TOKEN is missing. Configure it in the Agent environment file."
        )
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {AGENT_API_TOKEN}",
        "X-Agent-Token": AGENT_API_TOKEN,
        "User-Agent": "Nexora-FixOps-Agent/1.0",
    }


def _post_event(event: dict[str, Any]) -> dict[str, Any]:
    url = f"{CENTRAL_API_URL}/api/incidents"
    body = json.dumps(event, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=_headers(), method="POST")

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            status = response.status
            response_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise IncidentDeliveryError(
            f"Backend returned HTTP {exc.code}: {response_body[:500]}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise IncidentDeliveryError(f"Backend connection failed: {exc}") from exc

    if not 200 <= status < 300:
        raise IncidentDeliveryError(
            f"Backend returned unexpected HTTP {status}: {response_body[:500]}"
        )

    if not response_body.strip():
        return {"http_status": status}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return {"http_status": status, "response_text": response_body[:500]}


def _read_outbox() -> list[dict[str, Any]]:
    if not OUTBOX_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with OUTBOX_PATH.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        events.append(item)
                except json.JSONDecodeError:
                    logger.error("Ignoring invalid outbox line %s", line_number)
    except OSError:
        logger.exception("Could not read local incident outbox: %s", OUTBOX_PATH)
    return events


def _write_outbox(events: list[dict[str, Any]]) -> None:
    """Replace the JSONL file atomically to avoid a half-written queue."""
    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        try:
            OUTBOX_PATH.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove empty outbox")
        return

    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(OUTBOX_PATH.parent),
            prefix=f"{OUTBOX_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            for event in events:
                temporary.write(json.dumps(event, ensure_ascii=False) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, OUTBOX_PATH)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _queue_event(event: dict[str, Any]) -> None:
    with _outbox_lock:
        queued = _read_outbox()
        key = event["event_key"]
        if not any(item.get("event_key") == key for item in queued):
            queued.append(event)
            _write_outbox(queued)
            logger.warning("Incident saved locally for retry: %s", key)
        else:
            logger.info("Incident already exists in local outbox: %s", key)


def flush_outbox() -> int:
    """
    Retry queued events in order.
    Returns the number delivered. Stops at the first failure to preserve order.
    """
    delivered = 0
    with _outbox_lock:
        queued = _read_outbox()
        remaining: list[dict[str, Any]] = []

        for index, event in enumerate(queued):
            last_error: Exception | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    _post_event(event)
                    delivered += 1
                    logger.info(
                        "Queued incident delivered: %s", event.get("event_key")
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Outbox delivery attempt %s/%s failed for %s: %s",
                        attempt,
                        MAX_ATTEMPTS,
                        event.get("event_key"),
                        exc,
                    )
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(min(2 ** (attempt - 1), 4))

            if last_error is not None:
                remaining.extend(queued[index:])
                _write_outbox(remaining)
                return delivered

        _write_outbox(remaining)
    return delivered


def send_incident(event: dict[str, Any]) -> dict[str, Any]:
    """
    Public callback used by monitoring.py.

    Returns only after the Backend confirms a 2xx response. If delivery fails,
    the event is saved locally and an exception is raised. This is important:
    monitoring.py must not mark a queued-but-unsent event as transmitted.
    """
    completed = _complete_event(event)

    # First try to deliver older events, then send the current event.
    flush_outbox()

    try:
        response = _post_event(completed)
        logger.info("Incident accepted by Backend: %s", completed["event_key"])
        return response
    except Exception as exc:
        _queue_event(completed)
        raise IncidentDeliveryError(
            f"Incident {completed['event_key']} was queued locally, not transmitted: {exc}"
        ) from exc


def pending_count() -> int:
    """Number of incidents waiting in the local outbox."""
    with _outbox_lock:
        return len(_read_outbox())
