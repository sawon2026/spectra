"""Research Context Manager — structured context for planners/LLMs; never authorization."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from spectra.capabilities.registry import CapabilityRegistry
from spectra.cases.service import CaseService
from spectra.intelligence.goal import ResearchGoal
from spectra.intelligence.observation import Observation
from spectra.intelligence.state import InvestigationState
from spectra.intelligence.task import Task
from spectra.knowledge.graph import KnowledgeGraph, NodeType
from spectra.knowledge.memory import CaseMemory
from spectra.knowledge.observation_repo import ObservationRepository
from spectra.models.scope import Scope

# Lazy import FindingEngine inside methods to avoid circular import:
# findings → intelligence.observation → intelligence.__init__ → context → findings


class ResearchContext(BaseModel):
    """Snapshot of investigation context.

    Explicitly NOT authorization. NOT evidence by itself. NOT executable.
    """

    case_id: UUID
    goal_text: str = ""
    task_type: str = ""
    scope_summary: dict[str, Any] = Field(default_factory=dict)
    available_capabilities: list[str] = Field(default_factory=list)
    plan_steps: list[str] = Field(default_factory=list)
    recent_observations: list[dict[str, Any]] = Field(default_factory=list)
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    memory_hints: list[str] = Field(default_factory=list)
    graph_node_counts: dict[str, int] = Field(default_factory=dict)
    decision_notes: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This context is advisory only. It does not authorize execution, "
        "change scope, or constitute evidence."
    )


class ResearchContextManager:
    """Gather structured context for adaptive planning / optional LLM."""

    def __init__(
        self,
        case_service: CaseService,
        registry: CapabilityRegistry,
        finding_engine: Any = None,
        memory: CaseMemory | None = None,
        graph: KnowledgeGraph | None = None,
        observation_repo: ObservationRepository | None = None,
    ) -> None:
        self.cases = case_service
        self.registry = registry
        if finding_engine is not None:
            self.findings = finding_engine
        else:
            from spectra.knowledge.findings import FindingEngine

            self.findings = FindingEngine()
        self.memory = memory or CaseMemory()
        self.graph = graph or KnowledgeGraph()
        self.obs_repo = observation_repo or ObservationRepository()

    def build(
        self,
        case_id: UUID,
        goal: ResearchGoal | None = None,
        task: Task | None = None,
        state: InvestigationState | None = None,
        observations: list[Observation] | None = None,
    ) -> ResearchContext:
        scope: Scope | None = self.cases.get_scope(case_id)
        scope_summary: dict[str, Any] = {}
        if scope:
            scope_summary = {
                "auth_status": scope.auth_status.value,
                "ready_for_act": scope.ready_for_act,
                "network_profile": scope.network_profile.value,
                "allowed_activities": list(scope.allowed_activities or []),
            }

        caps = [c.name for c in self.registry.list()]
        plan_steps: list[str] = []
        if state:
            plan_steps = [f"{s.capability}:{s.status.value}" for s in state.current_plan]

        recent: list[dict[str, Any]] = []
        obs_list = observations or []
        if not obs_list and state:
            for oid in state.observation_ids[-10:]:
                o = self.obs_repo.get(oid)
                if o:
                    obs_list.append(o)
        for o in obs_list[-10:]:
            recent.append({
                "capability": o.capability,
                "status": o.status.value,
                "summary": (o.summary or "")[:300],
            })

        findings = self.findings.list_for_case(case_id, limit=20)
        findings_summary = [
            {"title": f.title, "severity": f.severity.value, "confidence": f.confidence}
            for f in findings
        ]

        memory_hints: list[str] = []
        query = (goal.text if goal else "") or (task.text if task else "") or ""
        if query:
            for entry, score in self.memory.similar(query, limit=3):
                memory_hints.append(f"{entry.title} (score={score:.2f})")

        graph_counts: dict[str, int] = {}
        for nt in (NodeType.ARTIFACT, NodeType.FINDING, NodeType.EVIDENCE, NodeType.OBSERVATION):
            nodes = self.graph.nodes_by_type(case_id, nt, limit=100)
            graph_counts[nt.value] = len(nodes)

        return ResearchContext(
            case_id=case_id,
            goal_text=goal.text if goal else (task.text if task else ""),
            task_type=task.task_type.value if task else "",
            scope_summary=scope_summary,
            available_capabilities=caps,
            plan_steps=plan_steps,
            recent_observations=recent,
            findings_summary=findings_summary,
            memory_hints=memory_hints,
            graph_node_counts=graph_counts,
        )
