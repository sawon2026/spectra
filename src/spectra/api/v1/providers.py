"""AI provider discovery — never executes tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from spectra.ai.provider import ProviderRegistry
from spectra.api.deps import Principal, get_principal
from spectra.api.schemas.resources import ProviderOut

router = APIRouter()


@router.get("", response_model=list[ProviderOut])
def list_providers(principal: Principal = Depends(get_principal)) -> list[ProviderOut]:
    reg = ProviderRegistry()
    return [
        ProviderOut(
            name=i.name,
            available=i.available,
            offline=i.offline,
            model=i.model,
            capabilities=list(i.capabilities or []),
        )
        for i in reg.list_info()
    ]
