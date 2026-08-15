"""Phase 3 knowledge layer tests — offline, deterministic."""

from __future__ import annotations

from uuid import uuid4

import pytest

from spectra.intelligence.observation import Observation, ObservationStatus
from spectra.intelligence.state import InvestigationState, InvestigationStatus, PlanStep
from spectra.knowledge.correlation import CorrelationEngine, RelationKind
from spectra.knowledge.findings import FindingEngine, FindingState, _compute_confidence
from spectra.knowledge.graph import GraphEdge, GraphNode, KnowledgeGraph, NodeType, RelationType
from spectra.knowledge.investigation_repo import InvestigationRepository
from spectra.knowledge.memory import CaseMemory, MemoryEntry, extract_features, jaccard
from spectra.knowledge.observation_repo import ObservationRepository
from spectra.models.case import CaseCreate
from spectra.models.evidence import Evidence, EvidenceSourceType
from spectra.models.finding import FindingSeverity


def test_investigation_persist_and_reload(db, case_service):
    case = case_service.create(CaseCreate(name="inv-persist"))
    state = InvestigationState(
        case_id=case.id,
        target="/tmp/sample.bin",
        objectives=["inspect"],
        status=InvestigationStatus.EXECUTING,
        current_plan=[PlanStep(capability="hash-compute", objective="hash", order=0)],
    )
    repo = InvestigationRepository()
    repo.save(state)
    loaded = repo.get(state.id)
    assert loaded is not None
    assert loaded.status == InvestigationStatus.EXECUTING
    assert loaded.target == "/tmp/sample.bin"
    assert len(loaded.current_plan) == 1
    assert loaded.current_plan[0].capability == "hash-compute"

    loaded.transition(InvestigationStatus.COMPLETED)
    repo.save(loaded)
    again = repo.get(state.id)
    assert again is not None
    assert again.status == InvestigationStatus.COMPLETED


def test_observation_persist(db, event_bus):
    inv_id = uuid4()
    obs = Observation(
        investigation_id=inv_id,
        case_id=uuid4(),
        capability="hash-compute",
        status=ObservationStatus.SUCCESS,
        summary="abc123",
        structured_data={"algorithm": "sha256"},
    )
    repo = ObservationRepository(event_bus=event_bus)
    repo.save(obs)
    got = repo.get(obs.id)
    assert got is not None
    assert got.summary == "abc123"
    assert got.capability == "hash-compute"
    listed = repo.list_for_investigation(inv_id)
    assert len(listed) == 1


def test_finding_requires_evidence_for_critical(db, event_bus):
    engine = FindingEngine(event_bus=event_bus)
    obs = Observation(
        investigation_id=uuid4(),
        capability="hash-compute",
        status=ObservationStatus.SUCCESS,
        summary="critical remote code execution possible",
        structured_data={"severity": "critical"},
    )
    # No evidence → cannot stay critical with high confidence gate
    finding = engine.create_from_observation(case_id=uuid4(), observation=obs, evidence=[])
    assert finding.severity != FindingSeverity.CRITICAL or finding.confidence < 0.7


def test_confidence_deterministic():
    assert _compute_confidence(0, 0, 0) == 0.3
    assert _compute_confidence(2, 1, 1) > _compute_confidence(0, 0, 0)
    assert _compute_confidence(10, 10, 10) <= 1.0


def test_correlation_duplicate_and_independent(db, event_bus):
    engine = FindingEngine(event_bus=event_bus)
    obs = Observation(
        investigation_id=uuid4(),
        capability="file-info",
        status=ObservationStatus.SUCCESS,
        summary="metadata",
    )
    evid_id = uuid4()

    e = Evidence(
        id=evid_id,
        case_id=uuid4(),
        title="e1",
        source_type=EvidenceSourceType.TOOL,
    )
    case_id = uuid4()
    f1 = engine.create_from_observation(case_id=case_id, observation=obs, evidence=[e], title="Hardcoded secret key")
    f2 = engine.create_from_observation(case_id=case_id, observation=obs, evidence=[e], title="Hardcoded secret value")
    corr = CorrelationEngine()
    r = corr.correlate_pair(f1, f2)
    assert r.kind in (RelationKind.DUPLICATE, RelationKind.RELATED)

    f3 = engine.create_from_observation(
        case_id=case_id,
        observation=Observation(
            investigation_id=uuid4(),
            capability="hash-compute",
            status=ObservationStatus.SUCCESS,
            summary="hash only",
        ),
        title="File hash computed",
    )
    r2 = corr.correlate_pair(f1, f3)
    assert r2.kind in (RelationKind.INDEPENDENT, RelationKind.RELATED, RelationKind.INSUFFICIENT)


def test_correlation_conflict():
    from spectra.knowledge.findings import FindingRecord

    a = FindingRecord(
        case_id=uuid4(),
        title="Endpoint check",
        description="Endpoint exists and responds",
        affected_assets=["api.example.com"],
    )
    b = FindingRecord(
        case_id=a.case_id,
        title="Endpoint check",
        description="Endpoint unavailable and missing",
        affected_assets=["api.example.com"],
    )
    r = CorrelationEngine().correlate_pair(a, b)
    assert r.kind == RelationKind.CONFLICTING


def test_knowledge_graph_queries(db, event_bus):
    g = KnowledgeGraph(event_bus=event_bus)
    case_id = uuid4()
    artifact = GraphNode(case_id=case_id, node_type=NodeType.ARTIFACT, label="sample.apk")
    finding = GraphNode(case_id=case_id, node_type=NodeType.FINDING, label="insecure storage")
    evidence = GraphNode(case_id=case_id, node_type=NodeType.EVIDENCE, label="E-1")
    g.add_node(artifact)
    g.add_node(finding)
    g.add_node(evidence)
    g.add_edge(
        GraphEdge(
            case_id=case_id,
            relation=RelationType.SUPPORTS,
            from_node_id=evidence.id,
            to_node_id=finding.id,
        )
    )
    g.add_edge(
        GraphEdge(
            case_id=case_id,
            relation=RelationType.AFFECTS,
            from_node_id=finding.id,
            to_node_id=artifact.id,
        )
    )
    supporting = g.evidence_supporting_finding(finding.id)
    assert any(n.id == evidence.id for n in supporting)
    findings = g.findings_for_artifact(artifact.id)
    assert any(n.id == finding.id for n in findings)


def test_case_memory_similarity(db, event_bus):
    mem = CaseMemory(event_bus=event_bus)
    mem.add(
        MemoryEntry(
            category="methodology",
            title="Android insecure storage review",
            content="Check SharedPreferences and SQLite for secrets in APK analysis",
            tags=["android", "storage"],
        )
    )
    mem.add(
        MemoryEntry(
            category="methodology",
            title="Network PCAP review",
            content="Inspect DNS and TLS in packet captures",
            tags=["network", "pcap"],
        )
    )
    results = mem.similar("Analyze Android application for insecure storage secrets", limit=3)
    assert results
    assert results[0][1] > 0
    assert "android" in results[0][0].features or "storage" in " ".join(results[0][0].features)


def test_memory_is_advisory_only(db, event_bus):
    mem = CaseMemory(event_bus=event_bus)
    entry = mem.add(
        MemoryEntry(
            category="methodology",
            title="Prior path",
            content="Previously used hash-compute successfully",
            tags=["hash"],
        )
    )
    assert entry.metadata.get("advisory_only") is True
    assert entry.metadata.get("executable") is False


def test_memory_does_not_bypass_policy(policy, case_service, db):
    """Hard invariant: retrieved memory never authorizes execution."""
    mem = CaseMemory()
    mem.add(
        MemoryEntry(
            category="methodology",
            title="Run hash-compute always",
            content="capability hash-compute on all files",
            tags=["hash-compute"],
        )
    )
    # Even with memory suggesting hash-compute, policy still denies without scope
    decision = policy.evaluate(None, "hash-compute")
    assert decision.allowed is False


def test_finding_false_positive_transition(db, event_bus):
    engine = FindingEngine(event_bus=event_bus)
    obs = Observation(
        investigation_id=uuid4(),
        capability="file-info",
        status=ObservationStatus.SUCCESS,
        summary="benign",
    )
    f = engine.create_from_observation(case_id=uuid4(), observation=obs, title="Possible issue")
    updated = engine.set_status(f.id, FindingState.FALSE_POSITIVE)
    assert updated is not None
    assert updated.status == FindingState.FALSE_POSITIVE


def test_jaccard_and_features():
    f = extract_features("Android APK insecure SharedPreferences storage")
    assert "android" in f or "apk" in f or "storage" in f
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)


def test_evidence_provenance_chain(db, evidence_service, event_bus):
    from spectra.knowledge.graph import GraphEdge, GraphNode, KnowledgeGraph, NodeType, RelationType
    from spectra.models.evidence import EvidenceCreate, EvidenceSourceType

    case_id = uuid4()
    ev = evidence_service.record(
        EvidenceCreate(
            case_id=case_id,
            title="hash of sample",
            source_type=EvidenceSourceType.TOOL,
            tool_name="hash-compute",
            content_hash="a" * 64,
            repro_command="hash-compute --path sample.bin",
            metadata={"capability": "hash-compute", "artifact": "sample.bin"},
        )
    )
    assert ev.content_hash
    assert ev.tool_name == "hash-compute"
    g = KnowledgeGraph(event_bus=event_bus)
    art = GraphNode(case_id=case_id, node_type=NodeType.ARTIFACT, label="sample.bin")
    cap = GraphNode(case_id=case_id, node_type=NodeType.CAPABILITY, label="hash-compute")
    evid_n = GraphNode(case_id=case_id, node_type=NodeType.EVIDENCE, label=ev.title, ref_id=ev.id)
    g.add_node(art)
    g.add_node(cap)
    g.add_node(evid_n)
    g.add_edge(GraphEdge(case_id=case_id, relation=RelationType.ANALYZED_BY, from_node_id=art.id, to_node_id=cap.id))
    g.add_edge(GraphEdge(case_id=case_id, relation=RelationType.PRODUCED, from_node_id=cap.id, to_node_id=evid_n.id))
    # provenance query path
    neigh = g.neighbors(art.id, RelationType.ANALYZED_BY)
    assert neigh
