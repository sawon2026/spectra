"""Unified finding engine — evidence-driven, not AI-severity-driven."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import FindingRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.models.events import EventType, SpectraEvent
from spectra.models.evidence import Evidence
from spectra.models.finding import FindingSeverity

logger = get_logger(__name__)


class FindingState(str, Enum):
    NEW = "new"
    VALIDATED = "validated"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    NEEDS_REVIEW = "needs_review"


class FindingRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    investigation_id: UUID | None = None
    title: str
    description: str = ""
    severity: FindingSeverity = FindingSeverity.INFO
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = "other"
    affected_assets: list[str] = Field(default_factory=list)
    evidence_refs: list[UUID] = Field(default_factory=list)
    observation_refs: list[UUID] = Field(default_factory=list)
    remediation: str = ""
    status: FindingState = FindingState.NEW
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _compute_confidence(evidence_count: int, observation_success: int, tool_diversity: int) -> float:
    """Deterministic confidence rules — never AI-only elevation."""
    base = 0.3
    base += min(0.35, evidence_count * 0.15)
    base += min(0.25, observation_success * 0.1)
    base += min(0.15, tool_diversity * 0.1)
    return round(min(1.0, base), 3)


def _severity_from_signals(title: str, structured: dict[str, Any]) -> FindingSeverity:
    """Conservative mapping — defaults to INFO/LOW without strong signals."""
    t = title.lower()
    if structured.get("severity") in {s.value for s in FindingSeverity}:
        try:
            return FindingSeverity(structured["severity"])
        except ValueError:
            pass
    if any(k in t for k in ("critical", "rce", "remote code")):
        return FindingSeverity.HIGH
    if any(k in t for k in ("secret", "credential", "password", "api key")):
        return FindingSeverity.MEDIUM
    if any(k in t for k in ("hash", "metadata", "file type")):
        return FindingSeverity.INFO
    return FindingSeverity.LOW


class FindingEngine:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def create_from_observation(
        self,
        *,
        case_id: UUID,
        observation: Observation,
        evidence: list[Evidence] | None = None,
        title: str | None = None,
        category: str = "observation",
    ) -> FindingRecord:
        evidence = evidence or []
        if observation.status not in (ObservationStatus.SUCCESS,):
            conf = 0.2
        else:
            conf = _compute_confidence(
                evidence_count=len(evidence),
                observation_success=1,
                tool_diversity=1,
            )
        title = title or f"Observation from {observation.capability or 'unknown'}"
        severity = _severity_from_signals(title, observation.structured_data or {})
        if severity == FindingSeverity.CRITICAL and (conf < 0.7 or len(evidence) < 2):
            severity = FindingSeverity.HIGH
            conf = min(conf, 0.65)

        record = FindingRecord(
            case_id=case_id,
            investigation_id=observation.investigation_id,
            title=title,
            description=observation.summary[:2000],
            severity=severity,
            confidence=conf,
            evidence_quality=min(1.0, 0.4 + 0.2 * len(evidence)),
            category=category,
            evidence_refs=[e.id for e in evidence],
            observation_refs=[observation.id],
            status=FindingState.NEW if conf < 0.7 else FindingState.NEEDS_REVIEW,
            provenance={
                "capability": observation.capability,
                "source": observation.source,
                "observation_id": str(observation.id),
                "tool_result_keys": list((observation.structured_data or {}).keys()),
            },
        )
        self._persist(record)
        return record

    def set_status(self, finding_id: UUID, status: FindingState) -> FindingRecord | None:
        with get_session() as session:
            row = session.query(FindingRow).filter(FindingRow.id == finding_id).first()
            if not row:
                return None
            row.status = status.value
            row.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._row_to_record(row)

    def get(self, finding_id: UUID) -> FindingRecord | None:
        with get_session() as session:
            row = session.query(FindingRow).filter(FindingRow.id == finding_id).first()
            if not row:
                return None
            return self._row_to_record(row)

    def list_for_case(self, case_id: UUID, limit: int = 100) -> list[FindingRecord]:
        with get_session() as session:
            rows = (
                session.query(FindingRow)
                .filter(FindingRow.case_id == case_id)
                .order_by(FindingRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_record(r) for r in rows]

    def _persist(self, record: FindingRecord) -> None:
        with get_session() as session:
            session.add(
                FindingRow(
                    id=record.id,
                    case_id=record.case_id,
                    title=record.title,
                    severity=record.severity.value,
                    status=record.status.value,
                    category=record.category,
                    evidence_ids=[str(x) for x in record.evidence_refs],
                    location=",".join(record.affected_assets),
                    impact=record.description,
                    confidence=record.confidence,
                    remediation=record.remediation,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    metadata_={
                        **record.provenance,
                        "observation_refs": [str(x) for x in record.observation_refs],
                        "investigation_id": str(record.investigation_id) if record.investigation_id else None,
                        "evidence_quality": record.evidence_quality,
                        "finding_state": record.status.value,
                    },
                )
            )
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.FINDING_CREATED,
                    case_id=record.case_id,
                    message=f"Finding created: {record.title}",
                    payload={
                        "finding_id": str(record.id),
                        "severity": record.severity.value,
                        "confidence": record.confidence,
                    },
                    actor="finding_engine",
                )
            )
        logger.info("finding_created", finding_id=str(record.id), severity=record.severity.value)

    @staticmethod
    def _row_to_record(row: FindingRow) -> FindingRecord:
        meta = row.metadata_ or {}
        obs_refs = []
        for v in meta.get("observation_refs") or []:
            obs_refs.append(UUID(v) if isinstance(v, str) else v)
        evid = []
        for v in row.evidence_ids or []:
            evid.append(UUID(v) if isinstance(v, str) else v)
        try:
            state = FindingState(row.status)
        except ValueError:
            state = FindingState.NEW
        inv = meta.get("investigation_id")
        return FindingRecord(
            id=row.id,
            case_id=row.case_id,
            investigation_id=UUID(inv) if inv else None,
            title=row.title,
            description=row.impact or "",
            severity=FindingSeverity(row.severity),
            confidence=float(row.confidence or 0.5),
            evidence_quality=float(meta.get("evidence_quality") or 0.5),
            category=row.category or "other",
            affected_assets=[x for x in (row.location or "").split(",") if x],
            evidence_refs=evid,
            observation_refs=obs_refs,
            remediation=row.remediation or "",
            status=state,
            provenance={k: v for k, v in meta.items() if k not in ("observation_refs", "evidence_quality")},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
