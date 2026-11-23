
import os
import secrets
import subprocess

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader

router = APIRouter(prefix="/agent", tags=["Actions"])

header = APIKeyHeader(
    name="X-Agent-Key",
    auto_error=False
)

SERVICES = {
    "rh-service": "rh-service.service",
    "compta-service": "compta-service.service"
}

APPS = {
    "rh": "http://127.0.0.1:8101/health",
    "compta": "http://127.0.0.1:8102/health"
}


def authenticate(key: str = Depends(header)):
    expected = os.getenv("Nexora_AGENT_TOKEN")

    if not expected:
        raise HTTPException(503, "Token non configure")

    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(401, "Non autorise")


def get_unit(name):
    if name not in SERVICES:
        raise HTTPException(403, "Service interdit")
    return SERVICES[name]


def command(args):
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=15,
            check=False
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Commande expiree")
    except OSError:
        raise HTTPException(500, "Commande indisponible")


@router.get("/services/{name}/status")
def status(name: str, _=Depends(authenticate)):
    unit = get_unit(name)

    result = command([
        "/usr/bin/systemctl",
        "is-active",
        unit
    ])

    state = result.stdout.strip()

    return {
        "service": name,
        "state": state,
        "active": state == "active"
    }


@router.post("/services/{name}/restart")
def restart(name: str, _=Depends(authenticate)):
    unit = get_unit(name)

    result = command([
        "/usr/bin/sudo",
        "-n",
        "/usr/bin/systemctl",
        "restart",
        unit
    ])

    state = command([
        "/usr/bin/systemctl",
        "is-active",
        unit
    ]).stdout.strip()

    return {
        "service": name,
        "command_success": result.returncode == 0,
        "state": state,
        "success": result.returncode == 0 and state == "active"
    }


@router.get("/apps/{name}/health")
def health(name: str, _=Depends(authenticate)):
    if name not in APPS:
        raise HTTPException(403, "Application interdite")

    try:
        response = httpx.get(APPS[name], timeout=3)

        return {
            "app": name,
            "reachable": True,
            "http_status": response.status_code,
            "healthy": response.status_code == 200
        }

    except httpx.RequestError:
        return {
            "app": name,
            "reachable": False,
            "http_status": None,
            "healthy": False
        }


@router.get("/services/{name}/logs")
def logs(name: str, _=Depends(authenticate)):
    unit = get_unit(name)

    result = command([
        "/usr/bin/journalctl",
        "-u", unit,
        "-n", "30",
        "--no-pager",
        "--output=short"
    ])

    if result.returncode != 0:
        raise HTTPException(
            500, "Impossible de lire les logs"
        )

    return {
        "service": name,
        "logs": result.stdout[-12000:]
    }
