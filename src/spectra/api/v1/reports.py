"""Professional report export — FACT vs inference labels preserved."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from spectra.api.deps import Principal, get_principal, get_services

router = APIRouter()


def _build_report_data(case_id: UUID) -> dict:
    svc = get_services()
    case = svc.cases.get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    scope = svc.cases.get_scope(case_id)
    timeline = svc.timeline.list_for_case(case_id)
    evidence = svc.evidence.list_for_case(case_id)
    try:
        findings = svc.findings.list_for_case(case_id)
    except Exception:
        findings = []
    return {
        "case": {
            "id": str(case.id),
            "name": case.name,
            "description": getattr(case, "description", "") or "",
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
        },
        "scope": {
            "auth_status": scope.auth_status.value if scope and hasattr(scope.auth_status, "value") else (str(scope.auth_status) if scope else "unknown"),
            "network_profile": scope.network_profile.value if scope and hasattr(scope.network_profile, "value") else (str(scope.network_profile) if scope else "offline"),
            "ready_for_act": bool(getattr(scope, "ready_for_act", False)) if scope else False,
        },
        "methodology": {
            "policy_gate": "PolicyEngine",
            "network_default": "OFFLINE",
            "ai_as_fact": False,
        },
        "timeline": [
            {
                "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                "source": e.source,
                "summary": e.summary,
                "confidence": e.confidence,
            }
            for e in timeline
        ],
        "evidence": [
            {
                "id": str(e.id),
                "title": e.title,
                "source_type": e.source_type.value if hasattr(e.source_type, "value") else str(e.source_type),
                "content_hash": getattr(e, "content_hash", None),
                "confidence": float(getattr(e, "confidence", 1.0)),
            }
            for e in evidence
        ],
        "findings": [
            {
                "id": str(getattr(f, "id", "")),
                "title": getattr(f, "title", str(f)),
                "severity": getattr(f, "severity", "info") if not hasattr(getattr(f, "severity", None), "value") else f.severity.value,
                "confidence": float(getattr(f, "confidence", 0.5)),
            }
            for f in findings
        ],
    }


@router.get("/{case_id}/markdown")
def report_markdown(case_id: UUID, principal: Principal = Depends(get_principal)) -> PlainTextResponse:
    data = _build_report_data(case_id)
    lines = [
        f"# Spectra Report — {data['case']['name']}",
        "",
        "## Case",
        f"- ID: `{data['case']['id']}`",
        f"- Status: {data['case']['status']}",
        f"- Description: {data['case']['description'] or '(none)'}",
        "",
        "## Scope & methodology",
        f"- Auth: {data['scope']['auth_status']}",
        f"- Network: {data['scope']['network_profile']}",
        f"- Ready: {data['scope']['ready_for_act']}",
        "- All capability execution was policy-gated. Network default: OFFLINE.",
        "- AI inference is never labeled as FACT.",
        "",
        "## Timeline (labeled)",
    ]
    for e in data["timeline"]:
        lines.append(f"- **{e['kind']}** ({e['source']}): {e['summary']}")
    lines.extend(["", "## Evidence"])
    for e in data["evidence"]:
        h = e.get("content_hash") or "—"
        lines.append(f"- {e['title']} (hash={h}, conf={e['confidence']})")
    lines.extend(["", "## Findings"])
    for f in data["findings"]:
        lines.append(f"- [{f['severity']}] {f['title']} (conf={f['confidence']})")
    lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.get("/{case_id}/json")
def report_json(case_id: UUID, principal: Principal = Depends(get_principal)) -> Response:
    data = _build_report_data(case_id)
    return Response(json.dumps(data, indent=2, default=str), media_type="application/json")


@router.get("/{case_id}/html")
def report_html(case_id: UUID, principal: Principal = Depends(get_principal)) -> HTMLResponse:
    data = _build_report_data(case_id)
    tl = "".join(
        f"<li><strong>{e['kind']}</strong> ({e['source']}): {e['summary']}</li>" for e in data["timeline"]
    )
    ev = "".join(f"<li>{e['title']} <code>{e.get('content_hash') or ''}</code></li>" for e in data["evidence"])
    fd = "".join(f"<li>[{f['severity']}] {f['title']}</li>" for f in data["findings"])
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Spectra Report — {data['case']['name']}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{border-bottom:2px solid #333}} h2{{color:#333;margin-top:1.5rem}}
code{{background:#f4f4f4;padding:0.1rem 0.3rem;border-radius:3px}}
.meta{{color:#555;font-size:0.9rem}}
.note{{background:#fff8e6;border-left:4px solid #e6a800;padding:0.75rem;margin:1rem 0}}
</style></head><body>
<h1>Spectra Report — {data['case']['name']}</h1>
<p class="meta">Case <code>{data['case']['id']}</code> · Status {data['case']['status']}</p>
<div class="note">AI inference is never labeled as FACT. PolicyEngine gated all capability execution.</div>
<h2>Scope</h2>
<ul><li>Auth: {data['scope']['auth_status']}</li><li>Network: {data['scope']['network_profile']}</li></ul>
<h2>Timeline</h2><ul>{tl or '<li>No entries</li>'}</ul>
<h2>Evidence</h2><ul>{ev or '<li>None</li>'}</ul>
<h2>Findings</h2><ul>{fd or '<li>None</li>'}</ul>
</body></html>"""
    return HTMLResponse(html)


@router.get("/{case_id}/pdf")
def report_pdf(case_id: UUID, principal: Principal = Depends(get_principal)) -> Response:
    """Minimal valid PDF export without heavy dependencies."""
    data = _build_report_data(case_id)
    lines = [
        f"Spectra Report - {data['case']['name']}",
        f"Case: {data['case']['id']}",
        f"Status: {data['case']['status']}",
        f"Auth: {data['scope']['auth_status']}  Network: {data['scope']['network_profile']}",
        "AI inference is never labeled as FACT.",
        "",
        "Timeline:",
    ]
    for e in data["timeline"][:40]:
        lines.append(f"- [{e['kind']}] {e['summary'][:80]}")
    lines.append("")
    lines.append("Evidence:")
    for e in data["evidence"][:40]:
        lines.append(f"- {e['title']}")
    lines.append("")
    lines.append("Findings:")
    for f in data["findings"][:40]:
        lines.append(f"- [{f['severity']}] {f['title']}")

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
