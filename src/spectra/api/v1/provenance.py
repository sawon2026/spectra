"""Provenance read API — investigation reproducibility."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from spectra.api.deps import Principal, get_principal, get_services

router = APIRouter()


@router.get("/by-case/{case_id}")
def list_provenance(
    case_id: UUID,
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    svc = get_services()
    links = svc.provenance.list_for_case(case_id, limit=limit)
    return [
        {
            "id": str(p.id),
            "case_id": str(p.case_id),
            "from_kind": p.from_kind.value if hasattr(p.from_kind, "value") else str(p.from_kind),
            "from_id": str(p.from_id),
            "to_kind": p.to_kind.value if hasattr(p.to_kind, "value") else str(p.to_kind),
            "to_id": str(p.to_id),
            "relation": p.relation,
            "content_hash": p.content_hash,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in links
    ]
