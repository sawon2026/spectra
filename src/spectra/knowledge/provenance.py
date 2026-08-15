"""Evidence provenance chain (Phase 6).

Artifact → Capability → Execution → Observation → Evidence → Finding → Report
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import ProvenanceLinkRow, get_session
from spectra.core.logging import get_logger

logger = get_logger(__name__)


class ProvenanceKind(str, Enum):
    ARTIFACT = "artifact"
    CAPABILITY = "capability"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    FINDING = "finding"
    REPORT = "report"
    WORKFLOW = "workflow"
    INVESTIGATION = "investigation"


class ProvenanceLink(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    from_kind: ProvenanceKind
    from_id: UUID
    to_kind: ProvenanceKind
    to_id: UUID
    relation: str = "produced"
    content_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProvenanceService:
    """Queryable provenance graph edges."""

    def link(
        self,
        case_id: UUID,
        from_kind: ProvenanceKind,
        from_id: UUID,
        to_kind: ProvenanceKind,
        to_id: UUID,
        *,
        relation: str = "produced",
        content_hash: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ProvenanceLink:
        edge = ProvenanceLink(
            case_id=case_id,
            from_kind=from_kind,
            from_id=from_id,
            to_kind=to_kind,
            to_id=to_id,
            relation=relation,
            content_hash=content_hash,
            payload=dict(payload or {}),
        )
        with get_session() as session:
            session.add(
                ProvenanceLinkRow(
                    id=edge.id,
                    case_id=edge.case_id,
                    from_kind=edge.from_kind.value,
                    from_id=edge.from_id,
                    to_kind=edge.to_kind.value,
                    to_id=edge.to_id,
                    relation=edge.relation,
                    content_hash=edge.content_hash,
                    payload=edge.payload,
                    created_at=edge.created_at,
                )
            )
        return edge

    def chain_for(self, entity_id: UUID, case_id: UUID | None = None) -> list[ProvenanceLink]:
        with get_session() as session:
            q = session.query(ProvenanceLinkRow).filter(
                (ProvenanceLinkRow.from_id == entity_id)
                | (ProvenanceLinkRow.to_id == entity_id)
            )
            if case_id:
                q = q.filter(ProvenanceLinkRow.case_id == case_id)
            rows = q.order_by(ProvenanceLinkRow.created_at.asc()).all()
            return [self._to_link(r) for r in rows]

    def list_for_case(self, case_id: UUID, limit: int = 500) -> list[ProvenanceLink]:
        with get_session() as session:
            rows = (
                session.query(ProvenanceLinkRow)
                .filter(ProvenanceLinkRow.case_id == case_id)
                .order_by(ProvenanceLinkRow.created_at.asc())
                .limit(limit)
                .all()
            )
            return [self._to_link(r) for r in rows]

    def upstream(self, entity_id: UUID) -> list[ProvenanceLink]:
        with get_session() as session:
            rows = (
                session.query(ProvenanceLinkRow)
                .filter(ProvenanceLinkRow.to_id == entity_id)
                .order_by(ProvenanceLinkRow.created_at.asc())
                .all()
            )
            return [self._to_link(r) for r in rows]

    def downstream(self, entity_id: UUID) -> list[ProvenanceLink]:
        with get_session() as session:
            rows = (
                session.query(ProvenanceLinkRow)
                .filter(ProvenanceLinkRow.from_id == entity_id)
                .order_by(ProvenanceLinkRow.created_at.asc())
                .all()
            )
            return [self._to_link(r) for r in rows]

    @staticmethod
    def _to_link(row: ProvenanceLinkRow) -> ProvenanceLink:
        return ProvenanceLink(
            id=row.id,
            case_id=row.case_id,
            from_kind=ProvenanceKind(row.from_kind),
            from_id=row.from_id,
            to_kind=ProvenanceKind(row.to_kind),
            to_id=row.to_id,
            relation=row.relation or "produced",
            content_hash=row.content_hash,
            payload=dict(row.payload or {}),
            created_at=row.created_at,
        )
