"""Capability registry API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from spectra.api.deps import Principal, get_principal, get_services
from spectra.api.schemas.resources import CapabilityOut

router = APIRouter()


@router.get("", response_model=list[CapabilityOut])
def list_capabilities(principal: Principal = Depends(get_principal)) -> list[CapabilityOut]:
    svc = get_services()
    caps = svc.caps.list()
    out: list[CapabilityOut] = []
    for c in caps:
        out.append(
            CapabilityOut(
                name=c.name if hasattr(c, "name") else str(c),
                category=getattr(c, "category", "") or "",
                risk_level=getattr(c, "risk_level", "low")
                if not hasattr(getattr(c, "risk_level", None), "value")
                else c.risk_level.value,
                requires_authorization=bool(getattr(c, "requires_authorization", True)),
                description=getattr(c, "description", "") or "",
            )
        )
    return out
