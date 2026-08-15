"""Durable Workflow persistence and recovery helpers (Phase 6)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from spectra.core.db import WorkflowRow, get_session
from spectra.core.logging import get_logger

if TYPE_CHECKING:
    from spectra.intelligence.workflow import InvestigationWorkflow, WorkflowStatus

logger = get_logger(__name__)

_ALLOWED: dict[str, set[str]] = {
    "created": {"running", "cancelled", "failed"},
    "running": {"paused", "blocked", "completed", "failed", "cancelled", "running"},
    "paused": {"running", "cancelled", "failed"},
    "blocked": {"running", "paused", "cancelled", "failed"},
    "completed": set(),
    "failed": {"running", "cancelled"},
    "cancelled": set(),
}


def can_transition(current: Any, target: Any) -> bool:
    cur = current.value if hasattr(current, "value") else str(current)
    tgt = target.value if hasattr(target, "value") else str(target)
    return tgt in _ALLOWED.get(cur, set())


class WorkflowRepository:
    """Persist InvestigationWorkflow so process restart does not lose state."""

    def save(self, wf: InvestigationWorkflow) -> InvestigationWorkflow:
        wf.updated_at = datetime.now(UTC)
        with get_session() as session:
            row = session.query(WorkflowRow).filter(WorkflowRow.id == wf.id).first()
            goal_json = wf.goal.model_dump(mode="json") if wf.goal else {}
            data = dict(
                case_id=wf.case_id,
                investigation_id=wf.investigation_id,
                task_id=wf.task_id,
                status=wf.status.value,
                goal_json=goal_json,
                decision_history=[d.model_dump(mode="json") for d in wf.decision_history],
                observation_ids=[str(x) for x in wf.observation_ids],
                evidence_refs=[str(x) for x in wf.metadata.get("evidence_refs", [])],
                finding_ids=[str(x) for x in wf.metadata.get("finding_ids", [])],
                plan_revisions=list(wf.metadata.get("plan_revisions", [])),
                retries=dict(wf.metadata.get("retries", {})),
                last_step_id=wf.metadata.get("last_step_id"),
                last_execution_token=wf.metadata.get("last_execution_token"),
                recovery_notes=str(wf.metadata.get("recovery_notes", "")),
                metadata_=dict(wf.metadata),
                updated_at=wf.updated_at,
            )
            if row is None:
                row = WorkflowRow(id=wf.id, created_at=wf.created_at, **data)
                session.add(row)
            else:
                for k, v in data.items():
                    setattr(row, k, v)
        logger.info("workflow_saved", workflow_id=str(wf.id), status=wf.status.value)
        return wf

    def get(self, workflow_id: UUID) -> InvestigationWorkflow | None:
        with get_session() as session:
            row = session.query(WorkflowRow).filter(WorkflowRow.id == workflow_id).first()
            if not row:
                return None
            return self._to_workflow(row)

    def list_for_case(self, case_id: UUID, limit: int = 50) -> list[InvestigationWorkflow]:
        with get_session() as session:
            rows = (
                session.query(WorkflowRow)
                .filter(WorkflowRow.case_id == case_id)
                .order_by(WorkflowRow.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_workflow(r) for r in rows]

    def list_recoverable(self, limit: int = 100) -> list[InvestigationWorkflow]:
        recoverable = {"created", "running", "paused", "blocked"}
        with get_session() as session:
            rows = (
                session.query(WorkflowRow)
                .filter(WorkflowRow.status.in_(recoverable))
                .order_by(WorkflowRow.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_workflow(r) for r in rows]

    def transition(self, wf: InvestigationWorkflow, target: WorkflowStatus, reason: str = "") -> InvestigationWorkflow:
        if not can_transition(wf.status, target):
            raise ValueError(f"Invalid workflow transition: {wf.status.value} → {target.value}")
        prev = wf.status
        wf.status = target
        wf.record_decision(
            "transition",
            f"{prev.value} → {target.value}" + (f": {reason}" if reason else ""),
            {"from": prev.value, "to": target.value},
        )
        return self.save(wf)

    @staticmethod
    def _to_workflow(row: WorkflowRow) -> InvestigationWorkflow:
        from spectra.intelligence.goal import ResearchGoal
        from spectra.intelligence.workflow import (
            DecisionRecord,
            InvestigationWorkflow,
            WorkflowStatus,
        )

        goal = None
        if row.goal_json:
            try:
                goal = ResearchGoal.model_validate(row.goal_json)
            except Exception:
                goal = None
        decisions = []
        for d in row.decision_history or []:
            try:
                decisions.append(DecisionRecord.model_validate(d))
            except Exception:
                continue
        obs_ids = []
        for x in row.observation_ids or []:
            obs_ids.append(UUID(x) if isinstance(x, str) else x)
        meta = dict(row.metadata_ or {})
        meta.setdefault("evidence_refs", list(row.evidence_refs or []))
        meta.setdefault("finding_ids", list(row.finding_ids or []))
        meta.setdefault("plan_revisions", list(row.plan_revisions or []))
        meta.setdefault("retries", dict(row.retries or {}))
        if row.last_step_id:
            meta["last_step_id"] = str(row.last_step_id)
        if row.last_execution_token:
            meta["last_execution_token"] = row.last_execution_token
        if row.recovery_notes:
            meta["recovery_notes"] = row.recovery_notes
        return InvestigationWorkflow(
            id=row.id,
            case_id=row.case_id,
            goal=goal,
            investigation_id=row.investigation_id,
            task_id=row.task_id,
            status=WorkflowStatus(row.status),
            decision_history=decisions,
            observation_ids=obs_ids,
            metadata=meta,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
