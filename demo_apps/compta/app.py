
from pathlib import Path
from fastapi import FastAPI, HTTPException
from demo_apps.compta.data import INVOICES

app = FastAPI(title="FixOps Compta Service")

FAIL_FILE = Path("/tmp/fixops-compta-unhealthy")


@app.get("/health")
def health():
    if FAIL_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="Compta service unhealthy"
        )

    return {"service": "compta", "status": "healthy"}


@app.get("/invoices")
def get_invoices():
    return INVOICES


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    for invoice in INVOICES:
        if invoice["id"] == invoice_id:
            return invoice

    raise HTTPException(
        status_code=404,
        detail="Invoice not found"
    )
