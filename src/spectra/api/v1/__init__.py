"""API v1 routers."""

from fastapi import APIRouter

from spectra.api.v1 import (
    audit,
    auth,
    capabilities,
    cases,
    events,
    export,
    findings,
    graph,
    health,
    plugins,
    provenance,
    providers,
    reports,
    timeline,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(findings.router, prefix="/findings", tags=["findings"])
api_router.include_router(provenance.router, prefix="/provenance", tags=["provenance"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(capabilities.router, prefix="/capabilities", tags=["capabilities"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
