"""Deterministic finding/observation correlation."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from uuid import UUID

from pydantic import BaseModel

from spectra.knowledge.findings import FindingRecord


class RelationKind(str, Enum):
    DUPLICATE = "duplicate"
    RELATED = "related"
    INDEPENDENT = "independent"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient_evidence"


class CorrelationResult(BaseModel):
    left_id: UUID
    right_id: UUID
    kind: RelationKind
    score: float = 0.0
    reason: str = ""


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 2}


class CorrelationEngine:
    """Rule-based correlation — no LLM required."""

    def correlate_pair(self, a: FindingRecord, b: FindingRecord) -> CorrelationResult:
        if a.id == b.id:
            return CorrelationResult(left_id=a.id, right_id=b.id, kind=RelationKind.DUPLICATE, score=1.0, reason="same id")

        shared_ev = set(a.evidence_refs) & set(b.evidence_refs)
        shared_obs = set(a.observation_refs) & set(b.observation_refs)
        ta, tb = _tokens(a.title), _tokens(b.title)
        overlap = len(ta & tb) / max(1, len(ta | tb))

        if shared_ev and overlap > 0.5:
            return CorrelationResult(
                left_id=a.id, right_id=b.id, kind=RelationKind.DUPLICATE, score=0.9, reason="shared evidence + title overlap"
            )
        assets_a, assets_b = set(a.affected_assets), set(b.affected_assets)
        if assets_a and assets_b and assets_a & assets_b:
            neg = ("unavailable", "missing", "not found", "absent")
            pos = ("exists", "found", "present", "detected", "responds")
            da, db = a.description.lower(), b.description.lower()
            if (any(n in da for n in neg) and any(p in db for p in pos)) or (
                any(n in db for n in neg) and any(p in da for p in pos)
            ):
                return CorrelationResult(
                    left_id=a.id, right_id=b.id, kind=RelationKind.CONFLICTING, score=0.8, reason="opposing signals on asset"
                )

        if shared_ev or shared_obs:
            return CorrelationResult(
                left_id=a.id, right_id=b.id, kind=RelationKind.RELATED, score=0.7, reason="shared evidence/observation"
            )
        if overlap > 0.4:
            return CorrelationResult(
                left_id=a.id, right_id=b.id, kind=RelationKind.RELATED, score=overlap, reason="title token overlap"
            )

        if not a.evidence_refs and not b.evidence_refs:
            return CorrelationResult(
                left_id=a.id, right_id=b.id, kind=RelationKind.INSUFFICIENT, score=0.2, reason="no evidence"
            )

        return CorrelationResult(
            left_id=a.id, right_id=b.id, kind=RelationKind.INDEPENDENT, score=0.0, reason="no shared signals"
        )

    def correlate_all(self, findings: Iterable[FindingRecord]) -> list[CorrelationResult]:
        items = list(findings)
        results: list[CorrelationResult] = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                results.append(self.correlate_pair(items[i], items[j]))
        return results
