"""Capability registry — machine-discoverable tools and skills."""

from __future__ import annotations

from spectra.core.db import CapabilityRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.capability import (
    Capability,
    CapabilityCategory,
    ExecutionMode,
    InputType,
    OutputType,
    RiskLevel,
)
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class CapabilityRegistry:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus or EventBus()

    def register(self, cap: Capability) -> Capability:
        with get_session() as session:
            existing = session.query(CapabilityRow).filter(CapabilityRow.name == cap.name).first()
            if existing:
                # update
                existing.version = cap.version
                existing.category = cap.category.value
                existing.description = cap.description
                existing.supported_platforms = cap.supported_platforms
                existing.input_types = [t.value for t in cap.input_types]
                existing.output_types = [t.value for t in cap.output_types]
                existing.prerequisites = cap.prerequisites
                existing.risk_level = cap.risk_level.value
                existing.requires_authorization = cap.requires_authorization
                existing.execution_mode = cap.execution_mode.value
                existing.default_timeout_seconds = cap.default_timeout_seconds
                existing.produces_evidence = cap.produces_evidence
                existing.health_status = cap.health_status
                existing.metadata_ = cap.metadata
                session.flush()
                result = self._to_model(existing)
            else:
                row = CapabilityRow(
                    id=cap.id,
                    name=cap.name,
                    version=cap.version,
                    category=cap.category.value,
                    description=cap.description,
                    supported_platforms=cap.supported_platforms,
                    input_types=[t.value for t in cap.input_types],
                    output_types=[t.value for t in cap.output_types],
                    prerequisites=cap.prerequisites,
                    risk_level=cap.risk_level.value,
                    requires_authorization=cap.requires_authorization,
                    execution_mode=cap.execution_mode.value,
                    default_timeout_seconds=cap.default_timeout_seconds,
                    produces_evidence=cap.produces_evidence,
                    health_status=cap.health_status,
                    metadata_=cap.metadata,
                )
                session.add(row)
                result = cap
        self._bus.publish(
            SpectraEvent(
                event_type=EventType.CAPABILITY_REGISTERED,
                message=f"Capability registered: {cap.name}",
                payload={"name": cap.name, "category": cap.category.value},
                actor="capability_registry",
            )
        )
        logger.info("capability_registered", name=cap.name, category=cap.category.value)
        return result

    def get(self, name: str) -> Capability | None:
        with get_session() as session:
            row = session.query(CapabilityRow).filter(CapabilityRow.name == name).first()
            if not row:
                return None
            return self._to_model(row)

    def list(
        self,
        category: CapabilityCategory | None = None,
        healthy_only: bool = False,
    ) -> list[Capability]:
        with get_session() as session:
            q = session.query(CapabilityRow)
            if category:
                q = q.filter(CapabilityRow.category == category.value)
            if healthy_only:
                q = q.filter(CapabilityRow.health_status == "healthy")
            rows = q.order_by(CapabilityRow.name).all()
            return [self._to_model(r) for r in rows]

    def set_health(self, name: str, status: str) -> None:
        with get_session() as session:
            row = session.query(CapabilityRow).filter(CapabilityRow.name == name).first()
            if row:
                row.health_status = status

    @staticmethod
    def _to_model(row: CapabilityRow) -> Capability:
        return Capability(
            id=row.id,
            name=row.name,
            version=row.version or "0.1.0",
            category=CapabilityCategory(row.category),
            description=row.description or "",
            supported_platforms=row.supported_platforms or [],
            input_types=[InputType(t) for t in (row.input_types or [])],
            output_types=[OutputType(t) for t in (row.output_types or [])],
            prerequisites=row.prerequisites or [],
            risk_level=RiskLevel(row.risk_level or "low"),
            requires_authorization=bool(row.requires_authorization),
            execution_mode=ExecutionMode(row.execution_mode or "local"),
            default_timeout_seconds=int(row.default_timeout_seconds or 300),
            produces_evidence=bool(row.produces_evidence),
            health_status=row.health_status or "unknown",
            metadata=row.metadata_ or {},
        )


def seed_builtin_capabilities(registry: CapabilityRegistry) -> None:
    """Register a minimal set of built-in, low-risk capabilities for Phase 1."""
    builtins = [
        Capability(
            name="file-info",
            category=CapabilityCategory.UTILITY,
            description="Identify file type and basic metadata (read-only).",
            input_types=[InputType.FILE],
            output_types=[OutputType.JSON, OutputType.EVIDENCE],
            risk_level=RiskLevel.NONE,
            requires_authorization=False,
            execution_mode=ExecutionMode.READ_ONLY,
            health_status="healthy",
        ),
        Capability(
            name="strings-extract",
            category=CapabilityCategory.REVERSE_ENGINEERING,
            description="Extract printable strings from a binary (read-only).",
            input_types=[InputType.BINARY, InputType.FILE],
            output_types=[OutputType.TEXT, OutputType.EVIDENCE],
            risk_level=RiskLevel.LOW,
            requires_authorization=True,
            execution_mode=ExecutionMode.READ_ONLY,
            health_status="healthy",
        ),
        Capability(
            name="hash-compute",
            category=CapabilityCategory.UTILITY,
            description="Compute cryptographic hashes of a file (read-only).",
            input_types=[InputType.FILE],
            output_types=[OutputType.JSON, OutputType.EVIDENCE],
            risk_level=RiskLevel.NONE,
            requires_authorization=False,
            execution_mode=ExecutionMode.READ_ONLY,
            health_status="healthy",
        ),
        Capability(
            name="android.apk.metadata",
            category=CapabilityCategory.ANDROID,
            description="Inspect APK zip structure, manifest presence, cert entries, sha256.",
            input_types=[InputType.APK, InputType.FILE],
            output_types=[OutputType.JSON, OutputType.EVIDENCE],
            risk_level=RiskLevel.LOW,
            requires_authorization=True,
            execution_mode=ExecutionMode.READ_ONLY,
            health_status="healthy",
        ),
    ]
    for cap in builtins:
        registry.register(cap)
