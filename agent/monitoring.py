"""
FixOps - Agent monitoring (Personne 1)

Place this file at: agent/monitoring.py

This module detects incidents on the Ubuntu VM. It does not execute repairs.
It calls reporter.send_incident(event), which must be implemented in agent/reporter.py.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Callable, Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from urllib.request import Request

logger = logging.getLogger("fixops.monitoring")

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "10"))
HOST_ID = os.getenv("HOST_ID", socket.gethostname())

# These URLs must match the ports used by the RH and Compta demo applications.
APPLICATIONS = {
    "rh-service": {
        "url": "http://127.0.0.1:8101/health",
        "app": "rh",
    },
    "compta-service": {
        "url": "http://127.0.0.1:8102/health",
        "app": "compta",
    },
}
DAILY_REPORT_UNIT = "compta-daily-report.service"
HTTP_TIMEOUT_SECONDS = 3
SYSTEMCTL_TIMEOUT_SECONDS = 3


def _run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a fixed systemctl query. No user-supplied shell command is executed."""
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        timeout=SYSTEMCTL_TIMEOUT_SECONDS,
        check=False,
    )


def _service_is_active(unit: str) -> bool:
    result = _run_systemctl("is-active", unit)
    return result.returncode == 0 and result.stdout.strip() == "active"


def _systemd_properties(unit: str) -> dict[str, str]:
    result = _run_systemctl(
        "show",
        unit,
        "--property=ActiveState",
        "--property=SubState",
        "--property=Result",
        "--property=ExecMainStatus",
    )
    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


def _check_health(url: str) -> tuple[str, int | None, str | None]:
    """
    Return (incident_type, HTTP status, detail).
    A 200 response means healthy; 503 means HEALTH_CHECK_FAILED;
    connection failures/timeouts mean APP_UNREACHABLE.
    """
    request = Request(url, headers={"User-Agent": "FixOps-Agent"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
        if status == 503:
            return "HEALTH_CHECK_FAILED", status, "Health endpoint returned HTTP 503"
        return "APP_UNREACHABLE", status, f"Unexpected HTTP status: {status}"
    except (URLError, TimeoutError, OSError) as exc:
        return "APP_UNREACHABLE", None, str(exc)

    if status == 200:
        return "OK", status, None
    if status == 503:
        return "HEALTH_CHECK_FAILED", status, "Health endpoint returned HTTP 503"
    return "APP_UNREACHABLE", status, f"Unexpected HTTP status: {status}"


def _incident(service: str, incident_type: str, observed_status: str,
              details: dict[str, Any]) -> dict[str, Any]:
    # Stable logical key: repeated polling cycles describe the same open condition.
    event_key = f"{HOST_ID}:{service}:{incident_type}"
    return {
        "source": "fixops-agent",
        "host_id": HOST_ID,
        "service": service,
        "type": incident_type,
        "observed_status": observed_status,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "event_key": event_key,
        "details": details,
    }


class Monitoring:
    """Poll the two demo applications and the daily-report oneshot job."""

    def __init__(self, report_callback: Callable[[dict[str, Any]], Any],
                 poll_seconds: int = POLL_SECONDS) -> None:
        self.report_callback = report_callback
        self.poll_seconds = max(1, poll_seconds)
        # An incident is reported once while its condition remains unchanged.
        self.active_incidents: set[str] = set()

    def _report_once(self, event: dict[str, Any]) -> None:
        key = event["event_key"]
        if key in self.active_incidents:
            return
        try:
            self.report_callback(event)
        except Exception:
            # Do not mark it as reported: the next cycle can retry if the backend
            # was temporarily unavailable. reporter.py should log and handle retries.
            logger.exception("Could not report incident %s", key)
            return
        self.active_incidents.add(key)
        logger.warning("Incident reported: %s", key)

    def _mark_recovered(self, service: str) -> None:
        # Remove all incident keys for this service so a later new failure is reported.
        prefix = f"{HOST_ID}:{service}:"
        self.active_incidents = {
            key for key in self.active_incidents if not key.startswith(prefix)
        }

    def check_application(self, unit: str, url: str) -> None:
        try:
            active = _service_is_active(unit)
        except (subprocess.TimeoutExpired, OSError):
            logger.exception("Could not read systemd state for %s", unit)
            return

        if not active:
            # Priority rule: do not check HTTP if systemd says the service is stopped.
            self._report_once(_incident(
                unit, "SERVICE_STOPPED", "inactive",
                {"systemd_state": "inactive"},
            ))
            return

        try:
            incident_type, http_status, detail = _check_health(url)
        except Exception:
            logger.exception("Health check failed unexpectedly for %s", unit)
            incident_type, http_status, detail = (
                "APP_UNREACHABLE", None, "Unexpected monitoring error"
            )

        if incident_type == "OK":
            self._mark_recovered(unit)
            logger.info("%s is active and healthy", unit)
            return

        self._report_once(_incident(
            unit,
            incident_type,
            f"http_{http_status}" if http_status is not None else "unreachable",
            {"http_status": http_status, "url": url, "error": detail},
        ))

    def check_daily_report(self) -> None:
        try:
            props = _systemd_properties(DAILY_REPORT_UNIT)
        except (subprocess.TimeoutExpired, OSError):
            logger.exception("Could not read systemd state for %s", DAILY_REPORT_UNIT)
            return

        active_state = props.get("ActiveState", "")
        result = props.get("Result", "")
        exit_status = props.get("ExecMainStatus", "")

        # A oneshot job is normally inactive/dead after a successful run.
        # Only report an actual failed result, not the normal inactive state.
        if active_state == "failed" or (result and result not in {"success", "exit-code"}
                                        and exit_status not in {"", "0"}):
            self._report_once(_incident(
                DAILY_REPORT_UNIT,
                "JOB_FAILED",
                "failed",
                {
                    "active_state": active_state,
                    "result": result,
                    "exec_main_status": exit_status,
                },
            ))
        elif result == "success" or (active_state == "inactive" and exit_status == "0"):
            self._mark_recovered(DAILY_REPORT_UNIT)

    def check_once(self) -> None:
        for unit, config in APPLICATIONS.items():
            self.check_application(unit, config["url"])
        self.check_daily_report()

    def run_forever(self) -> None:
        logger.info("FixOps monitoring started; interval=%s seconds", self.poll_seconds)
        while True:
            started = time.monotonic()
            self.check_once()
            elapsed = time.monotonic() - started
            time.sleep(max(0, self.poll_seconds - elapsed))


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # reporter.py is the separate Personne 1 module responsible for POST /api/incidents.
    try:
        from agent.reporter import send_incident
    except ImportError as exc:
        raise SystemExit(
            "agent.reporter.send_incident is not available yet. "
            "Create reporter.py before starting the monitoring loop."
        ) from exc

    Monitoring(report_callback=send_incident).run_forever()


if __name__ == "__main__":
    main()
