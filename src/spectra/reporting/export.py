"""Professional finding report export."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from spectra.knowledge.findings import FindingEngine, FindingRecord
from spectra.models.case import Case
from spectra.models.scope import Scope


class ReportBundle(BaseModel):
    case: dict[str, Any]
    scope: dict[str, Any] | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    methodology: str = "Spectra deterministic analysis with policy-gated tool execution."
    executive_summary: str = ""


class ReportExporter:
    def __init__(self, finding_engine: FindingEngine | None = None) -> None:
        self.findings = finding_engine or FindingEngine()

    def build(
        self,
        case: Case,
        scope: Scope | None = None,
        findings: list[FindingRecord] | None = None,
    ) -> ReportBundle:
        items = findings if findings is not None else self.findings.list_for_case(case.id)
        by_sev: dict[str, int] = {}
        for f in items:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        summary = (
            f"Case '{case.name}' — {len(items)} finding(s). "
            + ", ".join(f"{k}: {v}" for k, v in sorted(by_sev.items()))
        )
        return ReportBundle(
            case=case.model_dump(mode="json"),
            scope=scope.model_dump(mode="json") if scope else None,
            findings=[f.model_dump(mode="json") for f in items],
            executive_summary=summary,
        )

    def to_json(self, bundle: ReportBundle) -> str:
        return bundle.model_dump_json(indent=2)

    def to_markdown(self, bundle: ReportBundle) -> str:
        lines = [
            f"# Spectra Security Report: {bundle.case.get('name', 'case')}",
            "",
            f"_Generated: {bundle.generated_at}_",
            "",
            "## Executive Summary",
            "",
            bundle.executive_summary,
            "",
            "## Scope",
            "",
        ]
        if bundle.scope:
            lines.append(f"- Auth: `{bundle.scope.get('auth_status')}`")
            lines.append(f"- Network: `{bundle.scope.get('network_profile')}`")
            lines.append(f"- Ready: `{bundle.scope.get('ready_for_act')}`")
        else:
            lines.append("_No scope recorded._")
        lines += ["", "## Methodology", "", bundle.methodology, "", "## Findings", ""]
        if not bundle.findings:
            lines.append("_No findings._")
        for i, f in enumerate(bundle.findings, 1):
            lines += [
                f"### {i}. {f.get('title')}",
                "",
                f"- **Severity:** {f.get('severity')}",
                f"- **Confidence:** {f.get('confidence')}",
                f"- **Status:** {f.get('status')}",
                f"- **Category:** {f.get('category')}",
                f"- **Evidence refs:** {', '.join(str(x) for x in f.get('evidence_refs') or []) or 'none'}",
                f"- **Observation refs:** {', '.join(str(x) for x in f.get('observation_refs') or []) or 'none'}",
                "",
                f.get("description") or "",
                "",
                f"**Remediation:** {f.get('remediation') or 'n/a'}",
                "",
            ]
        lines += ["## Appendix", "", "All findings are evidence-backed. AI prose is never treated as evidence."]
        return "\n".join(lines)
