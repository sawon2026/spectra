"""Execution ledger read API — observability only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from spectra.api.deps import Principal, get_principal, get_services
from spectra.knowledge.execution_ledger import ExecutionLedger

router = APIRouter()


@router.get("/by-case/{case_id}")
def ledger_by_case(
    case_id: UUID,
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    get_services()
    entries = ExecutionLedger().list_for_case(case_id, limit=limit)
    return [e.model_dump(mode="json") for e in entries]


@router.get("/by-workflow/{workflow_id}")
def ledger_by_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    get_services()
    entries = ExecutionLedger().list_for_workflow(workflow_id, limit=limit)
    return [e.model_dump(mode="json") for e in entries]
