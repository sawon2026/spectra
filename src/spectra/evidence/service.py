"""Evidence storage with fixity (SHA-256)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from spectra.core.db import EvidenceRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.events import EventType, SpectraEvent
from spectra.models.evidence import Evidence, EvidenceCreate, EvidenceSourceType

logger = get_logger(__name__)


def compute_file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Compute content hash of a file. Raises on missing/unreadable file."""
    if not path.is_file():
        raise FileNotFoundError(f"Artifact not found: {path}")
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class EvidenceService:
    def __init__(self, event_bus: EventBus | None = None, case_root: Path | None = None) -> None:
        self._bus = event_bus or EventBus()
        self._case_root = case_root

    def record(self, data: EvidenceCreate, *, verify_hash: bool = True) -> Evidence:
        content_hash = data.content_hash
        if data.artifact_path and self._case_root and verify_hash:
            candidate = (self._case_root / data.artifact_path).resolve()
            try:
                candidate.relative_to(self._case_root.resolve())
            except ValueError as exc:
                raise ValueError("artifact_path escapes case root") from exc
            if candidate.is_file():
                content_hash = compute_file_hash(candidate)

        evidence = Evidence(
            case_id=data.case_id,
            title=data.title,
            source_type=data.source_type,
            source_ref=data.source_ref,
            content_hash=content_hash,
            artifact_path=data.artifact_path,
            repro_command=data.repro_command,
            raw_excerpt=data.raw_excerpt,
            confidence=data.confidence,
            tool_name=data.tool_name,
            metadata=data.metadata,
        )
        with get_session() as session:
            row = EvidenceRow(
                id=evidence.id,
                case_id=evidence.case_id,
                title=evidence.title,
                source_type=evidence.source_type.value,
                source_ref=evidence.source_ref,
                content_hash=evidence.content_hash,
                artifact_path=evidence.artifact_path,
                repro_command=evidence.repro_command,
                raw_excerpt=evidence.raw_excerpt,
                confidence=evidence.confidence,
                tool_name=evidence.tool_name,
                observed_at=evidence.observed_at,
                created_at=evidence.created_at,
                metadata_=evidence.metadata,
            )
            session.add(row)
        self._bus.publish(
            SpectraEvent(
                event_type=EventType.EVIDENCE_RECORDED,
                case_id=evidence.case_id,
                message=f"Evidence recorded: {evidence.title}",
                payload={
                    "evidence_id": str(evidence.id),
                    "source_type": evidence.source_type.value,
                    "has_hash": bool(evidence.content_hash),
                },
                actor="evidence_service",
            )
        )
        logger.info(
            "evidence_recorded",
            evidence_id=str(evidence.id),
            case_id=str(evidence.case_id),
            title=evidence.title,
        )
        return evidence

    def list_for_case(self, case_id: UUID, limit: int = 100) -> list[Evidence]:
        with get_session() as session:
            rows = (
                session.query(EvidenceRow)
                .filter(EvidenceRow.case_id == case_id)
                .order_by(EvidenceRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_model(r) for r in rows]

    def get(self, evidence_id: UUID) -> Evidence | None:
        with get_session() as session:
            row = session.query(EvidenceRow).filter(EvidenceRow.id == evidence_id).first()
            if not row:
                return None
            return self._to_model(row)

    @staticmethod
    def _to_model(row: EvidenceRow) -> Evidence:
        return Evidence(
            id=row.id,
            case_id=row.case_id,
            title=row.title,
            source_type=EvidenceSourceType(row.source_type),
            source_ref=row.source_ref or "",
            content_hash=row.content_hash,
            artifact_path=row.artifact_path,
            repro_command=row.repro_command or "",
            raw_excerpt=row.raw_excerpt or "",
            confidence=row.confidence or 1.0,
            tool_name=row.tool_name,
            observed_at=row.observed_at,
            created_at=row.created_at,
            metadata=row.metadata_ or {},
        )
