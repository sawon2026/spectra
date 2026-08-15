"""Unified investigation timeline (Phase 6).

AI-generated reasoning is never recorded as FACT.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import TimelineEntryRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class TimelineKind(str, Enum):
    FACT = "FACT"
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    DECISION = "DECISION"
    POLICY_DECISION = "POLICY_DECISION"
    EXECUTION = "EXECUTION"
    FINDING = "FINDING"
    REPLAN = "REPLAN"
    WORKFLOW = "WORKFLOW"
    RECOVERY = "RECOVERY"


class TimelineEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    investigation_id: UUID | None = None
    workflow_id: UUID | None = None
    kind: TimelineKind
    source: str = "system"
    summary: str = ""
    confidence: float | None = None
    references: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TimelineService:
    """Append-only auditable timeline."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.bus = event_bus

    def append(
        self,
        case_id: UUID,
        kind: TimelineKind,
        summary: str,
        *,
        investigation_id: UUID | None = None,
        workflow_id: UUID | None = None,
        source: str = "system",
        confidence: float | None = None,
        references: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TimelineEntry:
        if kind == TimelineKind.FACT and source.lower().startswith(("ai", "llm", "model")):
            raise ValueError("AI-generated content cannot be recorded as FACT")

        entry = TimelineEntry(
            case_id=case_id,
            investigation_id=investigation_id,
            workflow_id=workflow_id,
            kind=kind,
            source=source,
            summary=summary[:4000],
            confidence=confidence,
            references=list(references or []),
            payload=dict(payload or {}),
        )
        with get_session() as session:
            session.add(
                TimelineEntryRow(
                    id=entry.id,
                    case_id=entry.case_id,
                    investigation_id=entry.investigation_id,
                    workflow_id=entry.workflow_id,
                    kind=entry.kind.value,
                    source=entry.source,
                    summary=entry.summary,
                    confidence=entry.confidence,
                    references=entry.references,
                    payload=entry.payload,
                    created_at=entry.created_at,
                )
            )
        if self.bus:
            self.bus.publish(
                SpectraEvent(
                    event_type=EventType.AUDIT,
                    case_id=case_id,
                    message=f"timeline:{kind.value}",
                    payload={"entry_id": str(entry.id), "kind": kind.value},
                    actor="timeline",
                )
            )
        return entry

    def list_for_case(
        self,
        case_id: UUID,
        *,
        kinds: list[TimelineKind] | None = None,
        limit: int = 200,
    ) -> list[TimelineEntry]:
        with get_session() as session:
            q = session.query(TimelineEntryRow).filter(TimelineEntryRow.case_id == case_id)
            if kinds:
                q = q.filter(TimelineEntryRow.kind.in_([k.value for k in kinds]))
            rows = q.order_by(TimelineEntryRow.created_at.asc()).limit(limit).all()
            return [self._to_entry(r) for r in rows]

    def list_for_investigation(
        self, investigation_id: UUID, limit: int = 200
    ) -> list[TimelineEntry]:
        with get_session() as session:
            rows = (
                session.query(TimelineEntryRow)
                .filter(TimelineEntryRow.investigation_id == investigation_id)
                .order_by(TimelineEntryRow.created_at.asc())
                .limit(limit)
                .all()
            )
            return [self._to_entry(r) for r in rows]

    @staticmethod
    def _to_entry(row: TimelineEntryRow) -> TimelineEntry:
        return TimelineEntry(
            id=row.id,
            case_id=row.case_id,
            investigation_id=row.investigation_id,
            workflow_id=row.workflow_id,
            kind=TimelineKind(row.kind),
            source=row.source or "system",
            summary=row.summary or "",
            confidence=row.confidence,
            references=list(row.references or []),
            payload=dict(row.payload or {}),
            created_at=row.created_at,
        )
