"""Case memory — advisory methodology knowledge only.

Memory NEVER bypasses PolicyEngine or becomes executable recipes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import MemoryEntryRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class MemoryEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID | None = None
    category: str  # methodology | evidence_pattern | false_positive | remediation | tool_compat
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def extract_features(text: str, extra_tags: list[str] | None = None) -> list[str]:
    """Deterministic feature extraction for similarity (no embeddings required)."""
    tokens = set()
    for raw in text.lower().replace("/", " ").replace(".", " ").split():
        t = "".join(c for c in raw if c.isalnum() or c == "-")
        if len(t) > 2:
            tokens.add(t)
    keywords = {
        "android", "apk", "ios", "binary", "elf", "pe", "malware", "yara",
        "secret", "credential", "storage", "sqlite", "sharedpreferences",
        "network", "api", "auth", "crypto", "hash", "strings", "manifest",
        "insecure", "hardcoded", "certificate", "pinning",
    }
    features = sorted(tokens & keywords)
    for tag in extra_tags or []:
        features.append(tag.lower())
    return sorted(set(features))


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class CaseMemory:
    """Persistent advisory memory with deterministic similarity retrieval."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        if not entry.features:
            entry.features = extract_features(f"{entry.title} {entry.content}", entry.tags)
        entry.metadata = {**entry.metadata, "advisory_only": True, "executable": False}
        with get_session() as session:
            session.add(
                MemoryEntryRow(
                    id=entry.id,
                    case_id=entry.case_id,
                    category=entry.category,
                    title=entry.title,
                    content=entry.content,
                    tags=entry.tags,
                    features=entry.features,
                    metadata_=entry.metadata,
                    created_at=entry.created_at,
                )
            )
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.MEMORY_ADDED,
                    case_id=entry.case_id,
                    message=f"Memory added: {entry.title}",
                    payload={"memory_id": str(entry.id), "category": entry.category},
                    actor="case_memory",
                )
            )
        logger.info("memory_added", memory_id=str(entry.id), category=entry.category)
        return entry

    def similar(
        self,
        query_text: str,
        *,
        tags: list[str] | None = None,
        limit: int = 5,
        min_score: float = 0.15,
    ) -> list[tuple[MemoryEntry, float]]:
        q_features = extract_features(query_text, tags)
        scored: list[tuple[MemoryEntry, float]] = []
        with get_session() as session:
            rows = session.query(MemoryEntryRow).order_by(MemoryEntryRow.created_at.desc()).limit(500).all()
            entries = [self._to_model(row) for row in rows]
        for entry in entries:
            score = jaccard(q_features, entry.features)
            if score >= min_score:
                scored.append((entry, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        results = scored[:limit]
        if self._bus and results:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.MEMORY_RETRIEVED,
                    message=f"Retrieved {len(results)} similar memory entries",
                    payload={"count": len(results), "top_score": results[0][1] if results else 0},
                    actor="case_memory",
                )
            )
        return results

    def list_for_case(self, case_id: UUID, limit: int = 50) -> list[MemoryEntry]:
        with get_session() as session:
            rows = (
                session.query(MemoryEntryRow)
                .filter(MemoryEntryRow.case_id == case_id)
                .order_by(MemoryEntryRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: MemoryEntryRow) -> MemoryEntry:
        return MemoryEntry(
            id=row.id,
            case_id=row.case_id,
            category=row.category,
            title=row.title,
            content=row.content or "",
            tags=list(row.tags or []),
            features=list(row.features or []),
            metadata=row.metadata_ or {},
            created_at=row.created_at,
        )
