from datetime import date

from fastapi import APIRouter

from services import data_registry as reg

router = APIRouter()

_PROVENANCE_FIELDS = ("source", "authority", "license", "limitations")


@router.get("/audit")
def audit():
    checks = []
    for d in reg.DATASETS:
        missing = [f for f in _PROVENANCE_FIELDS if not d.get(f)]
        issues = []
        if missing:
            issues.append(f"incomplete provenance: {', '.join(missing)}")
        if d["status"] == reg.Status.AVAILABLE.value and not d["analytical_eligible"]:
            issues.append("AVAILABLE but not analytically eligible (check intent)")
        if d["status"] != reg.Status.AVAILABLE.value and d["analytical_eligible"]:
            issues.append("non-AVAILABLE but flagged analytically eligible")
        if d["status"] == reg.Status.DEMO_ONLY.value and reg.can_use_for_analysis(d["id"]):
            issues.append("CRITICAL: demo data passes analytical gate")
        checks.append({
            "dataset": d["id"],
            "status": d["status"],
            "provenance_complete": not missing,
            "analytical_gate": reg.can_use_for_analysis(d["id"]),
            "issues": issues,
            "pass": not issues,
        })

    passed = sum(1 for c in checks if c["pass"])
    demo_leak = any("CRITICAL" in i for c in checks for i in c["issues"])
    return {
        "generated": date.today().isoformat(),
        "total": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "demo_data_leak": demo_leak,
        "provenance_complete_all": all(c["provenance_complete"] for c in checks),
        "checks": checks,
    }
