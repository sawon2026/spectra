"""Spectra intelligence layer — classifier, planner, state, observations, Phase 5 workflow.

This layer may REQUEST capability executions. It must never bypass
PolicyEngine or invoke unrestricted shell commands.
"""

from spectra.intelligence.adaptive import AdaptivePlanner
from spectra.intelligence.classifier import DeterministicClassifier, TaskClassifier
from spectra.intelligence.context import ResearchContext, ResearchContextManager
from spectra.intelligence.contracts import AIPlanResponse, ProposedStep, validate_ai_plan
from spectra.intelligence.goal import GoalEngine, GoalStatus, ResearchGoal
from spectra.intelligence.interpreter import Indicator, InterpretationResult, ObservationInterpreter
from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.orchestrator import InvestigationOrchestrator
from spectra.intelligence.planner import DeterministicPlanner, Plan, Planner
from spectra.intelligence.risk import ExecutionRisk, RiskAssessment, RiskConfidenceEvaluator
from spectra.intelligence.selection import CapabilityRequest, CapabilitySelectionEngine
from spectra.intelligence.state import (
    InvestigationState,
    InvestigationStatus,
    PlanStep,
    StepStatus,
)
from spectra.intelligence.task import ArtifactType, Task, TaskCreate, TaskType
from spectra.intelligence.workflow import (
    DecisionRecord,
    InvestigationWorkflow,
    WorkflowEngine,
    WorkflowStatus,
)

__all__ = [
    "Task",
    "TaskType",
    "ArtifactType",
    "TaskCreate",
    "InvestigationState",
    "StepStatus",
    "PlanStep",
    "InvestigationStatus",
    "Observation",
    "ObservationStatus",
    "TaskClassifier",
    "DeterministicClassifier",
    "Planner",
    "DeterministicPlanner",
    "Plan",
    "InvestigationOrchestrator",
    "ResearchGoal",
    "GoalStatus",
    "GoalEngine",
    "CapabilityRequest",
    "CapabilitySelectionEngine",
    "ObservationInterpreter",
    "Indicator",
    "InterpretationResult",
    "AdaptivePlanner",
    "InvestigationWorkflow",
    "WorkflowEngine",
    "WorkflowStatus",
    "DecisionRecord",
    "RiskConfidenceEvaluator",
    "RiskAssessment",
    "ExecutionRisk",
    "ResearchContext",
    "ResearchContextManager",
    "AIPlanResponse",
    "ProposedStep",
    "validate_ai_plan",
]
