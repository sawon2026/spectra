"""Execution ledger — observability only. Never authorizes capability execution.

Incomplete executions are marked recovery-required and must NOT be blindly replayed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import ExecutionLedgerRow, get_session
from spectra.core.logging import get_logger

logger = get_logger(__name__)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_RECOVERY_REQUIRED = "recovery_required"


class LedgerEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID | None = None
    step_id: UUID | None = None
    case_id: UUID | None = None
    capability: str = ""
    input_ref: str = ""
    policy_allowed: bool | None = None
    policy_reason: str = ""
    status: str = STATUS_PENDING
    started_at: datetime | None = None
    ended_at: datetime | None = None
    observation_id: UUID | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    failure_reason: str = ""
    recovery_state: str = ""
    actor: str = "system"
    request_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionLedger:
    """Durable step log for workflows — not a policy authority."""

    def record_start(
        self,
        *,
        workflow_id: UUID | None = None,
        step_id: UUID | None = None,
        case_id: UUID | None = None,
        capability: str = "",
        input_ref: str = "",
        policy_allowed: bool | None = None,
        policy_reason: str = "",
        actor: str = "system",
        request_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            workflow_id=workflow_id,
            step_id=step_id,
            case_id=case_id,
            capability=capability,
            input_ref=input_ref,
            policy_allowed=policy_allowed,
            policy_reason=policy_reason or "",
            status=STATUS_RUNNING if policy_allowed else STATUS_BLOCKED,
            started_at=datetime.now(UTC),
            actor=actor,
            request_id=request_id,
            metadata=dict(metadata or {}),
        )
        if policy_allowed is False:
            entry.status = STATUS_BLOCKED
            entry.ended_at = datetime.now(UTC)
            entry.failure_reason = policy_reason or "policy_denied"
        self._persist(entry)
        return entry

    def mark_completed(
        self,
        entry_id: UUID,
        *,
        observation_id: UUID | None = None,
        evidence_refs: list[str] | None = None,
    ) -> LedgerEntry | None:
        return self._update(
            entry_id,
            status=STATUS_COMPLETED,
            observation_id=observation_id,
            evidence_refs=evidence_refs or [],
            ended=True,
        )

    def mark_failed(self, entry_id: UUID, reason: str) -> LedgerEntry | None:
        return self._update(
            entry_id,
            status=STATUS_FAILED,
            failure_reason=reason,
            ended=True,
        )

    def mark_recovery_required(
        self, entry_id: UUID, reason: str = "incomplete_execution"
    ) -> LedgerEntry | None:
        return self._update(
            entry_id,
            status=STATUS_RECOVERY_REQUIRED,
            failure_reason=reason,
            recovery_state="awaiting_operator",
            ended=True,
        )

    def list_for_workflow(self, workflow_id: UUID, limit: int = 200) -> list[LedgerEntry]:
        with get_session() as session:
            rows = (
                session.query(ExecutionLedgerRow)
                .filter(ExecutionLedgerRow.workflow_id == workflow_id)
                .order_by(ExecutionLedgerRow.created_at.asc())
                .limit(limit)
                .all()
            )
            return [self._to_model(r) for r in rows]

    def list_for_case(self, case_id: UUID, limit: int = 200) -> list[LedgerEntry]:
        with get_session() as session:
            rows = (
                session.query(ExecutionLedgerRow)
                .filter(ExecutionLedgerRow.case_id == case_id)
                .order_by(ExecutionLedgerRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_model(r) for r in rows]

    def incomplete_for_workflow(self, workflow_id: UUID) -> list[LedgerEntry]:
        with get_session() as session:
            rows = (
                session.query(ExecutionLedgerRow)
                .filter(
                    ExecutionLedgerRow.workflow_id == workflow_id,
                    ExecutionLedgerRow.status.in_([STATUS_PENDING, STATUS_RUNNING]),
                )
                .all()
            )
            return [self._to_model(r) for r in rows]

    def _persist(self, entry: LedgerEntry) -> None:
        with get_session() as session:
            session.add(
                ExecutionLedgerRow(
                    id=entry.id,
                    workflow_id=entry.workflow_id,
                    step_id=entry.step_id,
                    case_id=entry.case_id,
                    capability=entry.capability,
                    input_ref=entry.input_ref,
                    policy_allowed=entry.policy_allowed,
                    policy_reason=entry.policy_reason,
                    status=entry.status,
                    started_at=entry.started_at,
                    ended_at=entry.ended_at,
                    observation_id=entry.observation_id,
                    evidence_refs=entry.evidence_refs,
                    failure_reason=entry.failure_reason,
                    recovery_state=entry.recovery_state,
                    actor=entry.actor,
                    request_id=entry.request_id,
                    metadata_=entry.metadata,
                    created_at=entry.created_at,
                )
            )
        logger.info(
            "ledger_entry",
            entry_id=str(entry.id),
            status=entry.status,
            capability=entry.capability,
        )

    def _update(
        self,
        entry_id: UUID,
        *,
        status: str,
        failure_reason: str = "",
        recovery_state: str = "",
        observation_id: UUID | None = None,
        evidence_refs: list[str] | None = None,
        ended: bool = False,
    ) -> LedgerEntry | None:
        with get_session() as session:
            row = session.query(ExecutionLedgerRow).filter(ExecutionLedgerRow.id == entry_id).first()
            if not row:
                return None
            row.status = status
            if failure_reason:
                row.failure_reason = failure_reason
            if recovery_state:
                row.recovery_state = recovery_state
            if observation_id is not None:
                row.observation_id = observation_id
            if evidence_refs is not None:
                row.evidence_refs = evidence_refs
            if ended:
                row.ended_at = datetime.now(UTC)
            session.flush()
            return self._to_model(row)

    @staticmethod
    def _to_model(row: ExecutionLedgerRow) -> LedgerEntry:
        return LedgerEntry(
            id=row.id,
            workflow_id=row.workflow_id,
            step_id=row.step_id,
            case_id=row.case_id,
            capability=row.capability or "",
            input_ref=row.input_ref or "",
            policy_allowed=row.policy_allowed,
            policy_reason=row.policy_reason or "",
            status=row.status,
            started_at=row.started_at,
            ended_at=row.ended_at,
            observation_id=row.observation_id,
            evidence_refs=list(row.evidence_refs or []),
            failure_reason=row.failure_reason or "",
            recovery_state=row.recovery_state or "",
            actor=row.actor or "system",
            request_id=row.request_id or "",
            metadata=dict(row.metadata_ or {}),
            created_at=row.created_at,
        )
