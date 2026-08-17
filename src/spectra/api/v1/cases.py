"""Cases and scopes API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from spectra.api.deps import Principal, ensure_write, get_principal, get_services
from spectra.api.schemas.resources import (
    CaseCreateIn,
    CaseOut,
    EvidenceCreateIn,
    EvidenceOut,
    ScopeCreateIn,
    ScopeOut,
)
from spectra.models.case import CaseCreate
from spectra.models.evidence import EvidenceCreate, EvidenceSourceType
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeCreate

router = APIRouter()


def _case_out(c) -> CaseOut:
    return CaseOut(
        id=c.id,
        name=c.name,
        description=getattr(c, "description", "") or "",
        status=c.status.value if hasattr(c.status, "value") else str(c.status),
        tags=list(getattr(c, "tags", []) or []),
        created_at=getattr(c, "created_at", None),
        updated_at=getattr(c, "updated_at", None),
    )


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreateIn,
    principal: Principal = Depends(get_principal),
) -> CaseOut:
    ensure_write(principal)
    svc = get_services()
    case = svc.cases.create(CaseCreate(name=body.name, description=body.description, tags=body.tags))
    return _case_out(case)


@router.get("", response_model=list[CaseOut])
def list_cases(
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[CaseOut]:
    svc = get_services()
    try:
        cases = svc.cases.list_cases(limit=limit)
    except Exception:
        cases = []
    return [_case_out(c) for c in cases]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: UUID, principal: Principal = Depends(get_principal)) -> CaseOut:
    svc = get_services()
    case = svc.cases.get(case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    return _case_out(case)


@router.put("/{case_id}/scope", response_model=ScopeOut)
def set_scope(
    case_id: UUID,
    body: ScopeCreateIn,
    principal: Principal = Depends(get_principal),
) -> ScopeOut:
    ensure_write(principal)
    svc = get_services()
    if not svc.cases.get(case_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        auth = AuthStatus(body.auth_status)
    except ValueError:
        auth = AuthStatus.PENDING
    try:
        net = NetworkProfile(body.network_profile)
    except ValueError:
        net = NetworkProfile.OFFLINE
    scope = svc.cases.set_scope(
        ScopeCreate(
            case_id=case_id,
            auth_status=auth,
            network_profile=net,
            allowed_activities=body.allowed_activities,
            forbidden_activities=body.forbidden_activities,
            auth_basis=body.auth_basis,
            notes=body.notes,
        )
    )
    return ScopeOut(
        id=scope.id,
        case_id=scope.case_id,
        auth_status=scope.auth_status.value if hasattr(scope.auth_status, "value") else str(scope.auth_status),
        network_profile=scope.network_profile.value
        if hasattr(scope.network_profile, "value")
        else str(scope.network_profile),
        allowed_activities=list(scope.allowed_activities or []),
        ready_for_act=bool(getattr(scope, "ready_for_act", False)),
    )


@router.get("/{case_id}/scope", response_model=ScopeOut)
def get_scope(case_id: UUID, principal: Principal = Depends(get_principal)) -> ScopeOut:
    svc = get_services()
    scope = svc.cases.get_scope(case_id)
    if not scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scope not found")
    return ScopeOut(
        id=scope.id,
        case_id=scope.case_id,
        auth_status=scope.auth_status.value if hasattr(scope.auth_status, "value") else str(scope.auth_status),
        network_profile=scope.network_profile.value
        if hasattr(scope.network_profile, "value")
        else str(scope.network_profile),
        allowed_activities=list(scope.allowed_activities or []),
        ready_for_act=bool(getattr(scope, "ready_for_act", False)),
    )


@router.post("/{case_id}/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
def create_evidence(
    case_id: UUID,
    body: EvidenceCreateIn,
    principal: Principal = Depends(get_principal),
) -> EvidenceOut:
    ensure_write(principal)
    svc = get_services()
    if not svc.cases.get(case_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        st = EvidenceSourceType(body.source_type)
    except ValueError:
        st = EvidenceSourceType.MANUAL
    ev = svc.evidence.record(
        EvidenceCreate(
            case_id=case_id,
            title=body.title,
            source_type=st,
            source_ref=body.source_ref,
            raw_excerpt=body.raw_excerpt,
            content_hash=body.content_hash,
            artifact_path=body.artifact_path,
            confidence=body.confidence,
        )
    )
    return EvidenceOut(
        id=ev.id,
        case_id=ev.case_id,
        title=ev.title,
        source_type=ev.source_type.value if hasattr(ev.source_type, "value") else str(ev.source_type),
        source_ref=getattr(ev, "source_ref", "") or "",
        content_hash=getattr(ev, "content_hash", None),
        confidence=float(getattr(ev, "confidence", 1.0)),
    )


@router.get("/{case_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[EvidenceOut]:
    svc = get_services()
    items = svc.evidence.list_for_case(case_id)
    return [
        EvidenceOut(
            id=e.id,
            case_id=e.case_id,
            title=e.title,
            source_type=e.source_type.value if hasattr(e.source_type, "value") else str(e.source_type),
            source_ref=getattr(e, "source_ref", "") or "",
            content_hash=getattr(e, "content_hash", None),
            confidence=float(getattr(e, "confidence", 1.0)),
        )
        for e in items
    ]
