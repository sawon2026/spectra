"""API v1 routers."""

from fastapi import APIRouter

from spectra.api.v1 import (
    audit,
    capabilities,
    cases,
    events,
    findings,
    graph,
    health,
    providers,
    reports,
    timeline,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(findings.router, prefix="/findings", tags=["findings"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(capabilities.router, prefix="/capabilities", tags=["capabilities"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
