"""Findings API — read-only listing (creation remains engine-driven)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from spectra.api.deps import Principal, get_principal, get_services
from spectra.api.schemas.resources import FindingOut

router = APIRouter()


@router.get("/by-case/{case_id}", response_model=list[FindingOut])
def list_findings(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[FindingOut]:
    svc = get_services()
    try:
        items = svc.findings.list_for_case(case_id)
    except Exception:
        items = []
    out: list[FindingOut] = []
    for f in items:
        out.append(
            FindingOut(
                id=f.id,
                case_id=getattr(f, "case_id", case_id),
                title=getattr(f, "title", str(f)),
                severity=getattr(f, "severity", "info")
                if not hasattr(getattr(f, "severity", None), "value")
                else f.severity.value,
                status=getattr(f, "status", "open")
                if not hasattr(getattr(f, "status", None), "value")
                else f.status.value,
                confidence=float(getattr(f, "confidence", 0.5)),
            )
        )
    return out
