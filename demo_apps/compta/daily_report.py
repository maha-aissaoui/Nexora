
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from demo_apps.compta.data import INVOICES

FAIL_FILE = Path("/tmp/fixops-daily-report-fail")
OUTPUT_FILE = Path("/tmp/fixops-daily-report.json")


def main():
    if FAIL_FILE.exists():
        print(
            "ERROR: Daily Report failed (simulation)",
            file=sys.stderr
        )
        return 1

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_invoices": len(INVOICES),
        "total_amount": sum(
            invoice["amount"] for invoice in INVOICES
        ),
        "currency": "TND",
        "status": "success"
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("Daily Report generated successfully")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
