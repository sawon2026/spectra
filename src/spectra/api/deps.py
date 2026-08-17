"""Shared FastAPI dependencies — services and auth-ready identity."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities
from spectra.cases.service import CaseService
from spectra.core.config import SpectraSettings, get_settings
from spectra.core.db import init_db
from spectra.core.migrations import ensure_schema
from spectra.events.bus import EventBus
from spectra.events.sse import get_sse_hub
from spectra.evidence.service import EvidenceService
from spectra.intelligence.workflow import WorkflowEngine
from spectra.knowledge.findings import FindingEngine
from spectra.knowledge.graph import KnowledgeGraph
from spectra.knowledge.provenance import ProvenanceService
from spectra.knowledge.timeline import TimelineService
from spectra.knowledge.workflow_repo import WorkflowRepository
from spectra.policy.engine import PolicyEngine
from spectra.reporting.export import ReportExporter
from spectra.tools.builtin import FileInfoAdapter, HashComputeAdapter


@dataclass
class Principal:
    """Auth-ready identity (offline-local by default)."""

    subject: str = "local"
    role: str = "admin"  # admin | researcher | viewer
    offline: bool = True


@dataclass
class AppServices:
    settings: SpectraSettings
    bus: EventBus
    policy: PolicyEngine
    cases: CaseService
    caps: CapabilityRegistry
    evidence: EvidenceService
    findings: FindingEngine
    workflows: WorkflowEngine
    workflow_repo: WorkflowRepository
    timeline: TimelineService
    provenance: ProvenanceService
    graph: KnowledgeGraph
    reports: ReportExporter


_services: AppServices | None = None


def get_services() -> AppServices:
    global _services
    if _services is None:
        settings = get_settings()
        init_db(settings)
        ensure_schema(settings)
        bus = EventBus(persist=True)
        hub = get_sse_hub()
        bus.subscribe(hub.on_event)
        policy = PolicyEngine(event_bus=bus)
        cases = CaseService(event_bus=bus)
        caps = CapabilityRegistry(event_bus=bus)
        seed_builtin_capabilities(caps)
        for adapter in (FileInfoAdapter(policy=policy, event_bus=bus), HashComputeAdapter(policy=policy, event_bus=bus)):
            with suppress(Exception):
                caps.register(adapter.capability)
        _services = AppServices(
            settings=settings,
            bus=bus,
            policy=policy,
            cases=cases,
            caps=caps,
            evidence=EvidenceService(event_bus=bus),
            findings=FindingEngine(event_bus=bus),
            workflows=WorkflowEngine(policy, caps, cases, bus),
            workflow_repo=WorkflowRepository(),
            timeline=TimelineService(event_bus=bus),
            provenance=ProvenanceService(),
            graph=KnowledgeGraph(),
            reports=ReportExporter(),
        )
    return _services


def reset_services() -> None:
    """Test helper — drop singleton."""
    global _services
    _services = None


def get_principal(
    request: Request,
    x_spectra_role: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve principal via AuthService (HMAC sessions / offline local)."""
    from spectra.auth.session import get_auth_service

    bearer: str | None = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization.removeprefix("Bearer ").strip()
    auth = get_auth_service()
    sess = auth.resolve(bearer, role_hint=x_spectra_role)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return Principal(subject=sess.subject, role=sess.role.value, offline=sess.offline)


def require_role(*allowed: str):
    def _check(principal: Principal = None) -> Principal:  # type: ignore[assignment]
        return principal

    return _check


def ensure_write(principal: Principal) -> None:
    if principal.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Viewer role is read-only")
