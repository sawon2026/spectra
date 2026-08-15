"""Report export API — distinguishes FACT vs inference in content."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from spectra.api.deps import Principal, get_principal, get_services

router = APIRouter()


@router.get("/{case_id}/markdown")
def report_markdown(case_id: UUID, principal: Principal = Depends(get_principal)) -> PlainTextResponse:
    svc = get_services()
    case = svc.cases.get(case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")
    timeline = svc.timeline.list_for_case(case_id)
    lines = [
        f"# Spectra Report — {case.name}",
        "",
        "## Scope & methodology",
        "All capability execution was policy-gated. Network default: OFFLINE.",
        "",
        "## Timeline (labeled)",
    ]
    for e in timeline:
        kind = e.kind.value if hasattr(e.kind, "value") else str(e.kind)
        lines.append(f"- **{kind}** ({e.source}): {e.summary}")
    lines.extend(["", "## Notes", "AI inference is never labeled as FACT.", ""])
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")
