"""Event bus for structured, auditable Spectra events."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from spectra.core.db import EventRow, get_session
from spectra.core.logging import get_logger
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class EventBus:
    def __init__(self, persist: bool = True) -> None:
        self.persist = persist
        self._buffer: list[SpectraEvent] = []

    def publish(self, event: SpectraEvent) -> SpectraEvent:
        self._buffer.append(event)
        if self.persist:
            with get_session() as session:
                session.add(
                    EventRow(
                        id=event.id,
                        event_type=event.event_type.value,
                        case_id=event.case_id,
                        message=event.message,
                        payload=event.payload,
                        actor=event.actor,
                        created_at=event.created_at,
                    )
                )
        logger.info(
            "event",
            event_type=event.event_type.value,
            case_id=str(event.case_id) if event.case_id else None,
            message=event.message[:200] if event.message else "",
        )
        return event

    def recent(self, case_id: UUID | None = None, limit: int = 50) -> list[SpectraEvent]:
        if not self.persist:
            items = self._buffer[-limit:]
            if case_id:
                items = [e for e in items if e.case_id == case_id]
            return items
        with get_session() as session:
            q = session.query(EventRow).order_by(EventRow.created_at.desc())
            if case_id:
                q = q.filter(EventRow.case_id == case_id)
            rows = q.limit(limit).all()
            return [
                SpectraEvent(
                    id=r.id,
                    event_type=EventType(r.event_type),
                    case_id=r.case_id,
                    message=r.message or "",
                    payload=r.payload or {},
                    actor=r.actor or "system",
                    created_at=r.created_at or datetime.now(timezone.utc),
                )
                for r in rows
            ]
