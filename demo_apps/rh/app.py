
from pathlib import Path
from fastapi import FastAPI, HTTPException  # pyright: ignore[reportMissingImports]

app = FastAPI(title="Nexora RH Service")

FAIL_FILE = Path("/tmp/nexora-rh-unhealthy")

EMPLOYEES = [
    {"id": 1, "name": "Ahmed", "department": "IT"},
    {"id": 2, "name": "Mariem", "department": "Marketing"},
    {"id": 3, "name": "Yassine", "department": "Comptabilite"}
]


@app.get("/health")
def health():
    if FAIL_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="RH service unhealthy"
        )
    return {"service": "rh", "status": "healthy"}


@app.get("/employees")
def get_employees():
    return EMPLOYEES


@app.get("/employees/{employee_id}")
def get_employee(employee_id: int):
    for employee in EMPLOYEES:
        if employee["id"] == employee_id:
            return employee

    raise HTTPException(
        status_code=404,
        detail="Employee not found"
    )
