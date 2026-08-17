"""Professional report export — FACT vs inference labels preserved."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from spectra.api.deps import Principal, get_principal, get_services
from spectra.reporting.export import ReportExporter

router = APIRouter()


def _bundle_for(case_id: UUID):
    svc = get_services()
    case = svc.cases.get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    scope = svc.cases.get_scope(case_id)
    timeline_raw = []
    provenance_raw = []
    evidence_count = 0
    try:
        timeline_raw = [
            {
                "kind": getattr(e.kind, "value", str(e.kind)),
                "source": getattr(e, "source", ""),
                "summary": getattr(e, "summary", ""),
                "confidence": getattr(e, "confidence", None),
            }
            for e in svc.timeline.list_for_case(case_id)
        ]
    except Exception:
        timeline_raw = []
    try:
        evidence_count = len(svc.evidence.list_for_case(case_id))
    except Exception:
        evidence_count = 0
    try:
        if hasattr(svc, "provenance") and svc.provenance is not None:
            links = (
                svc.provenance.list_for_case(case_id)
                if hasattr(svc.provenance, "list_for_case")
                else []
            )
            provenance_raw = [
                {
                    "from_kind": getattr(p.from_kind, "value", str(p.from_kind)),
                    "from_id": str(p.from_id),
                    "to_kind": getattr(p.to_kind, "value", str(p.to_kind)),
                    "to_id": str(p.to_id),
                    "relation": p.relation,
                }
                for p in links[:50]
            ]
    except Exception:
        provenance_raw = []
    findings = None
    try:
        findings = svc.findings.list_for_case(case_id)
    except Exception:
        findings = []
    exporter = ReportExporter()
    return exporter.build(
        case,
        scope,
        findings=findings,
        timeline=timeline_raw,
        provenance=provenance_raw,
        evidence_count=evidence_count,
    )


@router.get("/{case_id}/json")
def report_json(case_id: UUID, principal: Principal = Depends(get_principal)) -> dict:
    bundle = _bundle_for(case_id)
    return bundle.model_dump(mode="json")


@router.get("/{case_id}/markdown", response_class=PlainTextResponse)
def report_markdown(case_id: UUID, principal: Principal = Depends(get_principal)) -> str:
    bundle = _bundle_for(case_id)
    return ReportExporter().to_markdown(bundle)


@router.get("/{case_id}/html", response_class=HTMLResponse)
def report_html(case_id: UUID, principal: Principal = Depends(get_principal)) -> str:
    bundle = _bundle_for(case_id)
    return ReportExporter().to_html(bundle)


@router.get("/{case_id}/pdf")
def report_pdf(case_id: UUID, principal: Principal = Depends(get_principal)) -> Response:
    """Minimal valid PDF export without heavy dependencies."""
    bundle = _bundle_for(case_id)
    lines = [
        f"Spectra Report - {bundle.case.get('name')}",
        f"Case: {bundle.case.get('id')}",
        f"Status: {bundle.case.get('status')}",
        "AI inference is never labeled as FACT.",
        "",
        "Findings:",
    ]
    for f in bundle.findings[:40]:
        lines.append(f"- [{f.get('severity')}] {f.get('title')}")
    lines.append("")
    lines.append("Limitations:")
    lines.append(bundle.limitations[:200])

    content_ops = []
    y = 750
    for line in lines[:55]:
        safe = line.replace("\\", "/").replace("(", "[").replace(")", "]")[:90]
        content_ops.append(f"BT /F1 10 Tf 50 {y} Td ({safe}) Tj ET")
        y -= 14
        if y < 40:
            break
    stream = "\n".join(content_ops)
    objs = []
    objs.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj\n")
    objs.append("5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for o in objs:
        offsets.append(len(pdf))
        pdf += o
    xref = len(pdf)
    pdf += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return Response(
        content=pdf.encode("latin-1", errors="replace"),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="spectra-{case_id}.pdf"'},
    )
