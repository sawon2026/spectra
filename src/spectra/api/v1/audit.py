"""Audit log API — authorized read of security-relevant actions."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from spectra.api.deps import Principal, get_principal, get_services
from spectra.audit.service import AuditService

router = APIRouter()


class AuditOut(BaseModel):
    id: str
    action: str
    actor: str
    case_id: str | None = None
    message: str = ""
    created_at: str | None = None


@router.get("", response_model=list[AuditOut])
def list_audit(
    case_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    principal: Principal = Depends(get_principal),
) -> list[AuditOut]:
    svc = get_services()
    audit = AuditService(event_bus=svc.bus)
    entries = audit.list_recent(limit=limit, case_id=case_id)
    return [
        AuditOut(
            id=str(e.id),
            action=e.action,
            actor=e.actor,
            case_id=str(e.case_id) if e.case_id else None,
            message=e.message,
            created_at=e.created_at.isoformat() if e.created_at else None,
        )
        for e in entries
    ]
