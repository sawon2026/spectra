"""Capability Selection Engine — produces CapabilityRequests only, never executes."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.capabilities.registry import CapabilityRegistry
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.state import InvestigationState
from spectra.intelligence.task import ArtifactType, Task, TaskType
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import Scope

logger = get_logger(__name__)


class CapabilityRequest(BaseModel):
    """Structured request for a capability — not an executable command."""

    id: UUID = Field(default_factory=uuid4)
    capability: str = Field(..., min_length=1, max_length=128)
    inputs: dict[str, Any] = Field(default_factory=dict)
    objective: str = Field(default="", max_length=512)
    rationale: str = Field(default="", max_length=1024)
    priority: int = 0
    network_required: bool = False
    estimated_risk: str = "low"


class CapabilitySelectionEngine:
    """Deterministic selection of capabilities from goal/task/observations.

    Never executes. Only produces CapabilityRequests for the planner/orchestrator.
    """

    _ARTIFACT_MAP: dict[ArtifactType, list[str]] = {
        ArtifactType.APK: ["android.apk.metadata", "hash-compute", "strings-extract"],
        ArtifactType.BINARY: ["file-info", "hash-compute", "strings-extract"],
        ArtifactType.FILE: ["file-info", "hash-compute"],
        ArtifactType.TEXT: ["file-info", "hash-compute"],
        ArtifactType.UNKNOWN: ["file-info", "hash-compute"],
        ArtifactType.NONE: [],
    }

    _TASK_MAP: dict[TaskType, list[str]] = {
        TaskType.ANDROID: ["android.apk.metadata", "hash-compute", "strings-extract"],
        TaskType.BINARY: ["file-info", "hash-compute", "strings-extract"],
        TaskType.REVERSE_ENGINEERING: ["file-info", "strings-extract", "hash-compute"],
        TaskType.MALWARE: ["file-info", "hash-compute", "strings-extract"],
        TaskType.GENERAL: ["file-info", "hash-compute"],
        TaskType.UNKNOWN: ["file-info", "hash-compute"],
    }

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def select(
        self,
        task: Task,
        state: InvestigationState,
        registry: CapabilityRegistry,
        scope: Scope | None = None,
        observations: list[Observation] | None = None,
    ) -> list[CapabilityRequest]:
        available = {c.name: c for c in registry.list()}
        already = {s.capability for s in state.current_plan if s.status.value != "pending"}
        already |= {s.capability for s in state.completed_steps}
        already |= {s.capability for s in state.failed_steps}
        already |= {s.capability for s in state.blocked_steps}

        candidates: list[str] = []
        for name in task.requested_capabilities:
            if name not in candidates:
                candidates.append(name)
        for name in self._ARTIFACT_MAP.get(task.artifact_type, []):
            if name not in candidates:
                candidates.append(name)
        for name in self._TASK_MAP.get(task.task_type, []):
            if name not in candidates:
                candidates.append(name)
        for obs in observations or []:
            for name in self._suggest_from_observation(obs):
                if name not in candidates:
                    candidates.append(name)

        requests: list[CapabilityRequest] = []
        priority = 0
        for name in candidates:
            if name in already:
                continue
            cap = available.get(name)
            if cap is None:
                logger.info("capability_not_registered", capability=name)
                continue
            if scope and scope.forbidden_activities and name in scope.forbidden_activities:
                continue
            path = state.target or (task.metadata.get("artifact_path") if task.metadata else "") or ""
            inputs: dict[str, Any] = {}
            if path:
                inputs["path"] = path
            requests.append(
                CapabilityRequest(
                    capability=name,
                    inputs=inputs,
                    objective=f"select_{name}",
                    rationale=f"Selected for task_type={task.task_type.value} artifact={task.artifact_type.value}",
                    priority=priority,
                    network_required=bool(task.network_required),
                    estimated_risk=cap.risk_level.value if hasattr(cap.risk_level, "value") else str(cap.risk_level),
                )
            )
            priority += 1

        if self._bus and requests:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.CAPABILITY_SELECTED,
                    case_id=state.case_id,
                    message=f"Selected {len(requests)} capabilities",
                    payload={"capabilities": [r.capability for r in requests]},
                    actor="capability_selection",
                )
            )
        return requests

    def _suggest_from_observation(self, obs: Observation) -> list[str]:
        suggestions: list[str] = []
        summary = (obs.summary or "").lower()
        if obs.status != ObservationStatus.SUCCESS:
            return suggestions
        if any(k in summary for k in ("elf", "native", "shared object", "pe32", "mach-o")):
            suggestions.append("strings-extract")
        if any(k in summary for k in ("apk", "androidmanifest", "dex")):
            suggestions.append("android.apk.metadata")
            suggestions.append("strings-extract")
        if "hash" not in (obs.capability or ""):
            suggestions.append("hash-compute")
        return suggestions
