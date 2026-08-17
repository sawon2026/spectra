"""Case export / offline backup API — no secrets."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from spectra.api.deps import Principal, get_principal, get_services
from spectra.reporting.backup import CaseExportBundle, build_case_export, export_to_json

router = APIRouter()


@router.get("/cases/{case_id}")
def export_case(case_id: UUID, principal: Principal = Depends(get_principal)) -> dict:
    svc = get_services()
    case = svc.cases.get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    scope = svc.cases.get_scope(case_id)
    evidence_rows: list = []
    findings_rows: list = []
    timeline_rows: list = []
    provenance_rows: list = []
    nodes: list = []
    edges: list = []
    try:
        evidence_rows = [
            {
                "id": str(e.id),
                "title": e.title,
                "source_type": getattr(e.source_type, "value", str(e.source_type)),
                "content_hash": getattr(e, "content_hash", None),
                "confidence": float(getattr(e, "confidence", 1.0)),
            }
            for e in svc.evidence.list_for_case(case_id)
        ]
    except Exception:
        evidence_rows = []
    try:
        findings_rows = [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else {"title": str(f)}
            for f in svc.findings.list_for_case(case_id)
        ]
    except Exception:
        findings_rows = []
    try:
        timeline_rows = [
            {
                "id": str(getattr(t, "id", "")),
                "kind": getattr(getattr(t, "kind", None), "value", str(getattr(t, "kind", ""))),
                "source": getattr(t, "source", ""),
                "summary": getattr(t, "summary", ""),
            }
            for t in svc.timeline.list_for_case(case_id)
        ]
    except Exception:
        timeline_rows = []
    try:
        provenance_rows = [
            {
                "from_kind": getattr(p.from_kind, "value", str(p.from_kind)),
                "from_id": str(p.from_id),
                "to_kind": getattr(p.to_kind, "value", str(p.to_kind)),
                "to_id": str(p.to_id),
                "relation": p.relation,
            }
            for p in svc.provenance.list_for_case(case_id, limit=500)
        ]
    except Exception:
        provenance_rows = []
    try:
        from spectra.core.db import GraphEdgeRow, GraphNodeRow, get_session

        with get_session() as session:
            nodes = [
                {"id": str(r.id), "node_type": str(r.node_type or ""), "label": str(r.label or "")}
                for r in session.query(GraphNodeRow).filter(GraphNodeRow.case_id == case_id).limit(500).all()
            ]
            edges = [
                {
                    "id": str(r.id),
                    "relation": str(r.relation or ""),
                    "from_node_id": str(r.from_node_id),
                    "to_node_id": str(r.to_node_id),
                }
                for r in session.query(GraphEdgeRow).filter(GraphEdgeRow.case_id == case_id).limit(1000).all()
            ]
    except Exception:
        nodes, edges = [], []

    bundle = build_case_export(
        case=case.model_dump(mode="json"),
        scope=scope.model_dump(mode="json") if scope else None,
        evidence=evidence_rows,
        findings=findings_rows,
        timeline=timeline_rows,
        provenance=provenance_rows,
        graph_nodes=nodes,
        graph_edges=edges,
    )
    return bundle.model_dump(mode="json")


@router.get("/cases/{case_id}/json", response_class=PlainTextResponse)
def export_case_json_text(case_id: UUID, principal: Principal = Depends(get_principal)) -> str:
    data = export_case(case_id, principal)
    return export_to_json(CaseExportBundle.model_validate(data))
