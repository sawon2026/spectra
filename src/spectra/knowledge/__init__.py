"""Knowledge layer — findings, correlation, graph, case memory, timeline, provenance.

This layer never executes tools. PolicyEngine remains the execution gate.
"""

from spectra.knowledge.correlation import CorrelationEngine, RelationKind
from spectra.knowledge.findings import FindingEngine, FindingRecord, FindingState
from spectra.knowledge.graph import KnowledgeGraph, NodeType, RelationType
from spectra.knowledge.investigation_repo import InvestigationRepository
from spectra.knowledge.memory import CaseMemory, MemoryEntry
from spectra.knowledge.observation_repo import ObservationRepository
from spectra.knowledge.provenance import ProvenanceKind, ProvenanceLink, ProvenanceService
from spectra.knowledge.timeline import TimelineEntry, TimelineKind, TimelineService

__all__ = [
    "InvestigationRepository",
    "ObservationRepository",
    "FindingEngine",
    "FindingRecord",
    "FindingState",
    "CorrelationEngine",
    "RelationKind",
    "KnowledgeGraph",
    "NodeType",
    "RelationType",
    "CaseMemory",
    "MemoryEntry",
    "TimelineService",
    "TimelineEntry",
    "TimelineKind",
    "ProvenanceService",
    "ProvenanceLink",
    "ProvenanceKind",
]
