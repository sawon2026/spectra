"""Simple in-process event bus with optional persistence."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from spectra.core.db import EventRow, get_session
from spectra.core.logging import get_logger
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)

EventHandler = Callable[[SpectraEvent], None]


class EventBus:
    def __init__(self, persist: bool = True) -> None:
        self._handlers: list[EventHandler] = []
        self._persist = persist

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def publish(self, event: SpectraEvent) -> None:
        if self._persist:
            self._store(event)
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("event_handler_failed", event_type=event.event_type.value)

    def _store(self, event: SpectraEvent) -> None:
        try:
            with get_session() as session:
                row = EventRow(
                    id=event.id,
                    event_type=event.event_type.value,
                    case_id=event.case_id,
                    message=event.message,
                    payload=event.payload,
                    actor=event.actor,
                    created_at=event.created_at,
                )
                session.add(row)
        except Exception:
            logger.exception("event_persist_failed", event_type=event.event_type.value)

    def list_for_case(self, case_id: UUID, limit: int = 100) -> list[SpectraEvent]:
        with get_session() as session:
            rows = (
                session.query(EventRow)
                .filter(EventRow.case_id == case_id)
                .order_by(EventRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                SpectraEvent(
                    id=r.id,
                    event_type=EventType(r.event_type),
                    case_id=r.case_id,
                    message=r.message or "",
                    payload=r.payload or {},
                    actor=r.actor or "system",
                    created_at=r.created_at,
                )
                for r in rows
            ]
