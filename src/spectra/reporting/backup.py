"""Safe offline case export / backup bundles.

Exports never include secrets, tokens, or authentication material.
Designed for offline reproducibility of investigation metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class CaseExportBundle(BaseModel):
    """Deterministic JSON-serializable case backup (metadata only)."""

    format: str = "spectra.case.export.v1"
    exported_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    case: dict[str, Any]
    scope: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    graph_nodes: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)
    integrity: dict[str, Any] = Field(default_factory=dict)
    limitations: str = (
        "This export is investigation metadata only. "
        "Raw secrets, tokens, and API keys are never included. "
        "AI prose remains INFERENCE. PolicyEngine must still gate any re-execution."
    )


def build_case_export(
    *,
    case: dict[str, Any],
    scope: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, Any]] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    graph_nodes: list[dict[str, Any]] | None = None,
    graph_edges: list[dict[str, Any]] | None = None,
) -> CaseExportBundle:
    ev = list(evidence or [])
    fd = list(findings or [])
    tl = list(timeline or [])
    pr = list(provenance or [])
    nodes = list(graph_nodes or [])
    edges = list(graph_edges or [])
    return CaseExportBundle(
        case=case,
        scope=scope,
        evidence=ev,
        findings=fd,
        timeline=tl,
        provenance=pr,
        graph_nodes=nodes,
        graph_edges=edges,
        integrity={
            "evidence_count": len(ev),
            "finding_count": len(fd),
            "timeline_count": len(tl),
            "provenance_count": len(pr),
            "graph_node_count": len(nodes),
            "graph_edge_count": len(edges),
            "case_id": case.get("id"),
        },
    )


def export_to_json(bundle: CaseExportBundle) -> str:
    return bundle.model_dump_json(indent=2)
