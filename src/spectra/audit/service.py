"""Audit logging for security-relevant actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import EventRow, get_session
from spectra.events.sse import sanitize_payload
from spectra.models.events import EventType, SpectraEvent


class AuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    action: str
    actor: str = "system"
    case_id: UUID | None = None
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditService:
    """Persists audit events via EventBus/EventRow with audit.* types."""

    def __init__(self, event_bus: Any | None = None) -> None:
        self.bus = event_bus

    def record(
        self,
        action: str,
        *,
        actor: str = "system",
        case_id: UUID | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            actor=actor,
            case_id=case_id,
            message=message or action,
            metadata=sanitize_payload(metadata or {}),
        )
        if self.bus is not None:
            try:
                self.bus.publish(
                    SpectraEvent(
                        id=entry.id,
                        event_type=EventType.AUDIT,
                        case_id=case_id,
                        message=f"audit.{action}: {entry.message}"[:500],
                        payload={"action": action, **entry.metadata},
                        actor=actor,
                        created_at=entry.created_at,
                    )
                )
            except Exception:
                self._persist_direct(entry)
        else:
            self._persist_direct(entry)
        return entry

    def _persist_direct(self, entry: AuditEntry) -> None:
        with get_session() as session:
            session.add(
                EventRow(
                    id=entry.id,
                    event_type="audit",
                    case_id=entry.case_id,
                    message=f"audit.{entry.action}: {entry.message}"[:500],
                    payload={"action": entry.action, **entry.metadata},
                    actor=entry.actor,
                    created_at=entry.created_at,
                )
            )

    def list_recent(self, limit: int = 100, case_id: UUID | None = None) -> list[AuditEntry]:
        with get_session() as session:
            q = session.query(EventRow).filter(EventRow.event_type == "audit")
            if case_id:
                q = q.filter(EventRow.case_id == case_id)
            rows = q.order_by(EventRow.created_at.desc()).limit(limit).all()
            out: list[AuditEntry] = []
            for r in rows:
                payload = dict(r.payload or {})
                out.append(
                    AuditEntry(
                        id=UUID(str(r.id)),
                        action=str(payload.get("action", "unknown")),
                        actor=str(r.actor or "system"),
                        case_id=UUID(str(r.case_id)) if r.case_id else None,
                        message=str(r.message or ""),
                        metadata={k: v for k, v in payload.items() if k != "action"},
                        created_at=r.created_at,  # type: ignore[arg-type]
                    )
                )
            return out
