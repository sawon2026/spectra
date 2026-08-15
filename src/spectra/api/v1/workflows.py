"""Workflow control API — all execution remains policy-gated."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from spectra.api.deps import Principal, ensure_write, get_principal, get_services
from spectra.api.schemas.resources import WorkflowOut, WorkflowStartIn

router = APIRouter()


def _wf_out(wf) -> WorkflowOut:
    return WorkflowOut(
        id=wf.id,
        case_id=wf.case_id,
        status=wf.status.value if hasattr(wf.status, "value") else str(wf.status),
        investigation_id=wf.investigation_id,
        observation_ids=list(wf.observation_ids or []),
        decision_count=len(wf.decision_history or []),
        recovery_notes=str((wf.metadata or {}).get("recovery_notes", "")),
        metadata=dict(wf.metadata or {}),
    )


@router.post("/case/{case_id}/start", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
def start_workflow(
    case_id: UUID,
    body: WorkflowStartIn,
    principal: Principal = Depends(get_principal),
) -> WorkflowOut:
    ensure_write(principal)
    svc = get_services()
    if not svc.cases.get(case_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    # Policy is enforced inside WorkflowEngine / orchestrator / adapters
    wf, *_ = svc.workflows.start(case_id, body.goal, body.artifact_path, max_steps=body.max_steps)
    return _wf_out(wf)


@router.post("/{workflow_id}/pause", response_model=WorkflowOut)
def pause_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
) -> WorkflowOut:
    ensure_write(principal)
    svc = get_services()
    wf = svc.workflows.pause(workflow_id)
    if not wf:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot pause workflow")
    return _wf_out(wf)


@router.post("/{workflow_id}/resume", response_model=WorkflowOut)
def resume_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
) -> WorkflowOut:
    ensure_write(principal)
    svc = get_services()
    result = svc.workflows.resume(workflow_id)
    if not result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot resume workflow")
    wf, *_ = result
    return _wf_out(wf)


@router.post("/{workflow_id}/cancel", response_model=WorkflowOut)
def cancel_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
) -> WorkflowOut:
    ensure_write(principal)
    svc = get_services()
    wf = svc.workflows.cancel(workflow_id)
    if not wf:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot cancel workflow")
    return _wf_out(wf)


@router.post("/{workflow_id}/recover", response_model=WorkflowOut)
def recover_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
) -> WorkflowOut:
    ensure_write(principal)
    svc = get_services()
    wf = svc.workflows.recover(workflow_id)
    if not wf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _wf_out(wf)


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: UUID, principal: Principal = Depends(get_principal)) -> WorkflowOut:
    svc = get_services()
    wf = svc.workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _wf_out(wf)


@router.get("/by-case/{case_id}", response_model=list[WorkflowOut])
def list_workflows(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[WorkflowOut]:
    svc = get_services()
    return [_wf_out(w) for w in svc.workflows.list_for_case(case_id)]
