"""System health — no secrets."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from spectra import __version__
from spectra.ai.provider import ProviderRegistry
from spectra.api.deps import Principal, get_principal
from spectra.api.schemas.common import HealthResponse, RoleInfo
from spectra.core.config import get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    reg = ProviderRegistry()
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        offline_default=not settings.allow_network_by_default,
        ai_configured=reg.is_any_configured(),
    )


@router.get("/me", response_model=RoleInfo)
def me(principal: Principal = Depends(get_principal)) -> RoleInfo:
    return RoleInfo(subject=principal.subject, role=principal.role, offline=principal.offline)
