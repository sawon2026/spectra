"""Risk and Confidence Evaluator — deterministic, evidence-gated."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.models.finding import FindingSeverity


class ExecutionRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAssessment(BaseModel):
    severity: FindingSeverity = FindingSeverity.INFO
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    execution_risk: ExecutionRisk = ExecutionRisk.LOW
    rationale: str = ""
    conflicting: bool = False


class RiskConfidenceEvaluator:
    """Separates severity, confidence, evidence quality, and execution risk.

    LLM prose never increases severity. Critical requires strong evidence.
    Conflicting observations reduce confidence.
    """

    def assess_finding(
        self,
        finding,  # FindingRecord — imported lazily to avoid circular import
        observations: list[Observation] | None = None,
        evidence_count: int = 0,
    ) -> RiskAssessment:
        conf = finding.confidence
        eq = finding.evidence_quality
        sev = finding.severity
        conflicting = False

        obs = observations or []
        successes = sum(1 for o in obs if o.status == ObservationStatus.SUCCESS)
        failures = sum(1 for o in obs if o.status in (ObservationStatus.FAILED, ObservationStatus.TIMEOUT))
        if successes and failures:
            conflicting = True
            conf = min(conf, 0.45)
            eq = min(eq, 0.5)

        # Critical gate
        if sev == FindingSeverity.CRITICAL and (conf < 0.7 or evidence_count < 2):
            sev = FindingSeverity.HIGH
            conf = min(conf, 0.65)
            rationale = "Critical demoted: insufficient confidence or evidence"
        else:
            rationale = "Deterministic assessment from evidence and observations"

        from spectra.knowledge.findings import FindingState

        if finding.status == FindingState.FALSE_POSITIVE:
            conf = min(conf, 0.2)
            sev = FindingSeverity.INFO

        return RiskAssessment(
            severity=sev,
            confidence=round(conf, 3),
            evidence_quality=round(eq, 3),
            execution_risk=self._execution_risk(sev),
            rationale=rationale,
            conflicting=conflicting,
        )

    def assess_capability_execution(self, capability: str, risk_level: str) -> ExecutionRisk:
        mapping = {
            "none": ExecutionRisk.NONE,
            "low": ExecutionRisk.LOW,
            "medium": ExecutionRisk.MEDIUM,
            "high": ExecutionRisk.HIGH,
            "critical": ExecutionRisk.CRITICAL,
        }
        return mapping.get((risk_level or "low").lower(), ExecutionRisk.LOW)

    @staticmethod
    def _execution_risk(sev: FindingSeverity) -> ExecutionRisk:
        return {
            FindingSeverity.INFO: ExecutionRisk.NONE,
            FindingSeverity.LOW: ExecutionRisk.LOW,
            FindingSeverity.MEDIUM: ExecutionRisk.MEDIUM,
            FindingSeverity.HIGH: ExecutionRisk.HIGH,
            FindingSeverity.CRITICAL: ExecutionRisk.CRITICAL,
        }.get(sev, ExecutionRisk.LOW)
