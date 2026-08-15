"""Durable InvestigationState persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from spectra.core.db import InvestigationRow, get_session
from spectra.core.logging import get_logger
from spectra.intelligence.state import (
    InvestigationState,
    InvestigationStatus,
    PlanStep,
    StepStatus,
)

logger = get_logger(__name__)


def _step_to_dict(step: PlanStep) -> dict:
    return {
        "id": str(step.id),
        "capability": step.capability,
        "inputs": step.inputs,
        "objective": step.objective,
        "status": step.status.value,
        "observation_id": str(step.observation_id) if step.observation_id else None,
        "error": step.error,
        "order": step.order,
    }


def _step_from_dict(d: dict) -> PlanStep:
    return PlanStep(
        id=UUID(d["id"]) if isinstance(d.get("id"), str) else d.get("id"),
        capability=d.get("capability", ""),
        inputs=d.get("inputs") or {},
        objective=d.get("objective", ""),
        status=StepStatus(d.get("status", "pending")),
        observation_id=UUID(d["observation_id"]) if d.get("observation_id") else None,
        error=d.get("error"),
        order=int(d.get("order") or 0),
    )


class InvestigationRepository:
    def save(self, state: InvestigationState) -> InvestigationState:
        state.updated_at = datetime.now(timezone.utc)
        with get_session() as session:
            row = session.query(InvestigationRow).filter(InvestigationRow.id == state.id).first()
            data = dict(
                case_id=state.case_id,
                task_id=state.task_id,
                status=state.status.value,
                target=state.target,
                objectives=state.objectives,
                hypotheses=state.hypotheses,
                current_plan=[_step_to_dict(s) for s in state.current_plan],
                completed_steps=[_step_to_dict(s) for s in state.completed_steps],
                pending_steps=[_step_to_dict(s) for s in state.pending_steps],
                failed_steps=[_step_to_dict(s) for s in state.failed_steps],
                blocked_steps=[_step_to_dict(s) for s in state.blocked_steps],
                observation_ids=[str(x) for x in state.observation_ids],
                evidence_refs=[str(x) for x in state.evidence_refs],
                planner_version=state.planner_version,
                metadata_=state.metadata,
                updated_at=state.updated_at,
            )
            if row is None:
                row = InvestigationRow(
                    id=state.id,
                    created_at=state.created_at,
                    **data,
                )
                session.add(row)
            else:
                for k, v in data.items():
                    setattr(row, k, v)
        logger.info("investigation_saved", investigation_id=str(state.id), status=state.status.value)
        return state

    def get(self, investigation_id: UUID) -> InvestigationState | None:
        with get_session() as session:
            row = session.query(InvestigationRow).filter(InvestigationRow.id == investigation_id).first()
            if not row:
                return None
            return self._to_state(row)

    def list_for_case(self, case_id: UUID, limit: int = 50) -> list[InvestigationState]:
        with get_session() as session:
            rows = (
                session.query(InvestigationRow)
                .filter(InvestigationRow.case_id == case_id)
                .order_by(InvestigationRow.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_state(r) for r in rows]

    @staticmethod
    def _to_state(row: InvestigationRow) -> InvestigationState:
        def uuids(vals: list | None) -> list[UUID]:
            out: list[UUID] = []
            for v in vals or []:
                out.append(UUID(v) if isinstance(v, str) else v)
            return out

        return InvestigationState(
            id=row.id,
            case_id=row.case_id,
            task_id=row.task_id,
            status=InvestigationStatus(row.status),
            target=row.target or "",
            objectives=list(row.objectives or []),
            hypotheses=list(row.hypotheses or []),
            current_plan=[_step_from_dict(s) for s in (row.current_plan or [])],
            completed_steps=[_step_from_dict(s) for s in (row.completed_steps or [])],
            pending_steps=[_step_from_dict(s) for s in (row.pending_steps or [])],
            failed_steps=[_step_from_dict(s) for s in (row.failed_steps or [])],
            blocked_steps=[_step_from_dict(s) for s in (row.blocked_steps or [])],
            observation_ids=uuids(row.observation_ids),
            evidence_refs=uuids(row.evidence_refs),
            planner_version=row.planner_version or "deterministic-0.1",
            metadata=row.metadata_ or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
