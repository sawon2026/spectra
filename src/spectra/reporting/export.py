"""Professional investigation report export.

Findings are labeled by epistemic class so AI inference is never presented
as verified FACT. Reports remain reconstructible from case/scope/findings/
timeline/provenance data without requiring live tool execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from spectra.knowledge.findings import FindingEngine, FindingRecord
from spectra.models.case import Case
from spectra.models.scope import Scope

CLASS_FACT = "FACT"
CLASS_OBSERVATION = "OBSERVATION"
CLASS_EVIDENCE = "EVIDENCE"
CLASS_INFERENCE = "INFERENCE"
CLASS_HYPOTHESIS = "HYPOTHESIS"
CLASS_POLICY_DECISION = "POLICY_DECISION"
CLASS_FINDING = "FINDING"

LIMITATIONS_DEFAULT = (
    "This report is produced by Spectra under PolicyEngine-gated execution. "
    "AI-generated prose, if present, is classified as INFERENCE or HYPOTHESIS "
    "and is never authoritative evidence. Network defaults to OFFLINE. "
    "Findings without evidence_refs should be treated with lower confidence. "
    "Recovery never blindly replays potentially unsafe execution steps."
)


class ReportBundle(BaseModel):
    case: dict[str, Any]
    scope: dict[str, Any] | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    evidence_count: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    methodology: str = (
        "Spectra deterministic analysis with PolicyEngine as the sole execution gate. "
        "Controlled adapters only (shell=False, binary allowlist, metachar rejection)."
    )
    executive_summary: str = ""
    limitations: str = LIMITATIONS_DEFAULT
    classification_legend: dict[str, str] = Field(
        default_factory=lambda: {
            CLASS_FACT: "Verified fact from controlled observation or operator input",
            CLASS_OBSERVATION: "Raw observation from a policy-allowed capability",
            CLASS_EVIDENCE: "Persisted evidence with content hash / provenance",
            CLASS_INFERENCE: "Derived conclusion; not automatically FACT",
            CLASS_HYPOTHESIS: "Working hypothesis pending corroboration",
            CLASS_POLICY_DECISION: "PolicyEngine allow/deny decision",
            CLASS_FINDING: "Structured finding with severity and evidence refs",
        }
    )
    reproducibility: dict[str, Any] = Field(default_factory=dict)


class ReportExporter:
    def __init__(self, finding_engine: FindingEngine | None = None) -> None:
        self.findings = finding_engine or FindingEngine()

    def build(
        self,
        case: Case,
        scope: Scope | None = None,
        findings: list[FindingRecord] | None = None,
        *,
        timeline: list[dict[str, Any]] | None = None,
        provenance: list[dict[str, Any]] | None = None,
        evidence_count: int = 0,
    ) -> ReportBundle:
        items = findings if findings is not None else self.findings.list_for_case(case.id)
        by_sev: dict[str, int] = {}
        labeled: list[dict[str, Any]] = []
        for f in items:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            by_sev[sev] = by_sev.get(sev, 0) + 1
            d = f.model_dump(mode="json")
            d["epistemic_class"] = CLASS_FINDING
            d["description_class"] = CLASS_INFERENCE
            labeled.append(d)
        summary = (
            f"Case '{case.name}' — {len(items)} finding(s). "
            + ", ".join(f"{k}: {v}" for k, v in sorted(by_sev.items()))
        )
        return ReportBundle(
            case=case.model_dump(mode="json"),
            scope=scope.model_dump(mode="json") if scope else None,
            findings=labeled,
            timeline=list(timeline or []),
            provenance=list(provenance or []),
            evidence_count=evidence_count,
            executive_summary=summary,
            reproducibility={
                "policy_gate": "PolicyEngine",
                "offline_default": True,
                "shell": False,
                "schema_note": (
                    "Report reconstructible from persisted "
                    "case/scope/findings/timeline/provenance"
                ),
                "finding_count": len(items),
                "evidence_count": evidence_count,
                "timeline_count": len(timeline or []),
                "provenance_count": len(provenance or []),
            },
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
            "## Case Metadata",
            "",
            f"- **ID:** `{bundle.case.get('id')}`",
            f"- **Status:** {bundle.case.get('status')}",
            f"- **Tags:** {', '.join(bundle.case.get('tags') or []) or 'none'}",
            "",
            "## Scope",
            "",
        ]
        if bundle.scope:
            lines.append(f"- Auth: `{bundle.scope.get('auth_status')}`")
            lines.append(f"- Network: `{bundle.scope.get('network_profile')}`")
            lines.append(f"- Ready for act: `{bundle.scope.get('ready_for_act')}`")
            lines.append(f"- Allowed activities: {bundle.scope.get('allowed_activities') or []}")
        else:
            lines.append("_No scope recorded._")
        lines += ["", "## Classification Legend", ""]
        for k, v in bundle.classification_legend.items():
            lines.append(f"- **{k}:** {v}")
        lines += ["", "## Methodology", "", bundle.methodology, "", "## Findings", ""]
        if not bundle.findings:
            lines.append("_No findings._")
        for i, f in enumerate(bundle.findings, 1):
            lines += [
                f"### {i}. [{f.get('epistemic_class', CLASS_FINDING)}] {f.get('title')}",
                "",
                f"- **Severity:** {f.get('severity')}",
                f"- **Confidence:** {f.get('confidence')}",
                f"- **Status:** {f.get('status')}",
                f"- **Category:** {f.get('category')}",
                f"- **Description class:** {f.get('description_class', CLASS_INFERENCE)}",
                f"- **Evidence refs:** "
                f"{', '.join(str(x) for x in f.get('evidence_refs') or []) or 'none'}",
                f"- **Observation refs:** "
                f"{', '.join(str(x) for x in f.get('observation_refs') or []) or 'none'}",
                "",
                f.get("description") or "",
                "",
                f"**Remediation:** {f.get('remediation') or 'n/a'}",
                "",
            ]
        if bundle.timeline:
            lines += ["## Investigation Timeline", ""]
            for t in bundle.timeline[:50]:
                lines.append(
                    f"- `{t.get('kind') or t.get('event_type') or 'event'}` — "
                    f"{t.get('summary') or t.get('message') or ''}"
                )
            lines.append("")
        if bundle.provenance:
            lines += ["## Provenance (sample)", ""]
            for p in bundle.provenance[:30]:
                lines.append(
                    f"- {p.get('from_kind')} `{p.get('from_id')}` "
                    f"—[{p.get('relation')}]→ {p.get('to_kind')} `{p.get('to_id')}`"
                )
            lines.append("")
        lines += [
            "## Reproducibility",
            "",
            f"- Evidence count: {bundle.evidence_count}",
            f"- Finding count: {bundle.reproducibility.get('finding_count')}",
            f"- Timeline entries: {bundle.reproducibility.get('timeline_count')}",
            f"- Provenance links: {bundle.reproducibility.get('provenance_count')}",
            f"- Policy gate: {bundle.reproducibility.get('policy_gate')}",
            f"- Offline default: {bundle.reproducibility.get('offline_default')}",
            f"- shell=False: {bundle.reproducibility.get('shell') is False}",
            "",
            "## Limitations",
            "",
            bundle.limitations,
            "",
            "## Appendix",
            "",
            "All findings should be evidence-backed. "
            "AI prose is never treated as FACT or EVIDENCE.",
        ]
        return "\n".join(lines)

    def to_html(self, bundle: ReportBundle) -> str:
        md = self.to_markdown(bundle)
        body = (
            md.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>\n")
        )
        title = bundle.case.get("name", "case")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<title>Spectra Report — {title}</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:900px;"
            "margin:2rem auto;line-height:1.5;color:#111}"
            "h1,h2,h3{margin-top:1.4em}</style></head><body>"
            f"{body}</body></html>"
        )
