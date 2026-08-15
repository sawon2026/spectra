"""Timeline API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from spectra.api.deps import Principal, get_principal, get_services
from spectra.api.schemas.resources import TimelineEntryOut

router = APIRouter()


@router.get("/by-case/{case_id}", response_model=list[TimelineEntryOut])
def list_timeline(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[TimelineEntryOut]:
    svc = get_services()
    entries = svc.timeline.list_for_case(case_id)
    return [
        TimelineEntryOut(
            id=e.id,
            case_id=e.case_id,
            kind=e.kind.value if hasattr(e.kind, "value") else str(e.kind),
            source=e.source,
            summary=e.summary,
            confidence=e.confidence,
            created_at=e.created_at,
        )
        for e in entries
    ]
