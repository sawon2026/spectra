"""Durable Observation persistence."""

from __future__ import annotations

from uuid import UUID

from spectra.core.db import ObservationRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class ObservationRepository:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def save(self, obs: Observation) -> Observation:
        with get_session() as session:
            existing = session.query(ObservationRow).filter(ObservationRow.id == obs.id).first()
            if existing:
                existing.status = obs.status.value
                existing.summary = obs.summary
                existing.structured_data = obs.structured_data
                existing.evidence_refs = [str(x) for x in obs.evidence_refs]
                existing.confidence = obs.confidence
                existing.error = obs.error
            else:
                session.add(
                    ObservationRow(
                        id=obs.id,
                        investigation_id=obs.investigation_id,
                        case_id=obs.case_id,
                        source=obs.source,
                        capability=obs.capability,
                        status=obs.status.value,
                        summary=obs.summary,
                        structured_data=obs.structured_data,
                        evidence_refs=[str(x) for x in obs.evidence_refs],
                        confidence=obs.confidence,
                        error=obs.error,
                        created_at=obs.created_at,
                    )
                )
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.OBSERVATION_CREATED,
                    case_id=obs.case_id,
                    message=f"Observation persisted: {obs.capability} ({obs.status.value})",
                    payload={"observation_id": str(obs.id), "status": obs.status.value},
                    actor="observation_repo",
                )
            )
        logger.info(
            "observation_persisted",
            observation_id=str(obs.id),
            capability=obs.capability,
            status=obs.status.value,
        )
        return obs

    def get(self, observation_id: UUID) -> Observation | None:
        with get_session() as session:
            row = session.query(ObservationRow).filter(ObservationRow.id == observation_id).first()
            if not row:
                return None
            return self._to_model(row)

    def list_for_investigation(self, investigation_id: UUID, limit: int = 200) -> list[Observation]:
        with get_session() as session:
            rows = (
                session.query(ObservationRow)
                .filter(ObservationRow.investigation_id == investigation_id)
                .order_by(ObservationRow.created_at.asc())
                .limit(limit)
                .all()
            )
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: ObservationRow) -> Observation:
        refs = []
        for v in row.evidence_refs or []:
            refs.append(UUID(v) if isinstance(v, str) else v)
        return Observation(
            id=row.id,
            investigation_id=row.investigation_id,
            case_id=row.case_id,
            source=row.source or "executor",
            capability=row.capability or "",
            status=ObservationStatus(row.status),
            summary=row.summary or "",
            structured_data=row.structured_data or {},
            evidence_refs=refs,
            confidence=float(row.confidence or 1.0),
            error=row.error,
            created_at=row.created_at,
        )
