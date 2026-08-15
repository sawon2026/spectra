"""Lightweight knowledge graph over SQLite — no external graph DB."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from spectra.core.db import GraphEdgeRow, GraphNodeRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.events import EventType, SpectraEvent

logger = get_logger(__name__)


class NodeType(str, Enum):
    CASE = "case"
    INVESTIGATION = "investigation"
    ARTIFACT = "artifact"
    FILE = "file"
    ENDPOINT = "endpoint"
    CAPABILITY = "capability"
    TOOL = "tool"
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    FINDING = "finding"
    VULNERABILITY = "vulnerability"
    ASSET = "asset"


class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    ANALYZED_BY = "ANALYZED_BY"
    PRODUCED = "PRODUCED"
    SUPPORTS = "SUPPORTS"
    AFFECTS = "AFFECTS"
    RELATED_TO = "RELATED_TO"
    DUPLICATES = "DUPLICATES"
    DERIVED_FROM = "DERIVED_FROM"
    OBSERVED_IN = "OBSERVED_IN"
    CONFLICTS_WITH = "CONFLICTS_WITH"


class GraphNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID | None = None
    node_type: NodeType
    label: str = ""
    ref_id: UUID | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID | None = None
    relation: RelationType
    from_node_id: UUID
    to_node_id: UUID
    properties: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def add_node(self, node: GraphNode) -> GraphNode:
        with get_session() as session:
            session.add(
                GraphNodeRow(
                    id=node.id,
                    case_id=node.case_id,
                    node_type=node.node_type.value,
                    label=node.label,
                    ref_id=node.ref_id,
                    properties=node.properties,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        with get_session() as session:
            session.add(
                GraphEdgeRow(
                    id=edge.id,
                    case_id=edge.case_id,
                    relation=edge.relation.value,
                    from_node_id=edge.from_node_id,
                    to_node_id=edge.to_node_id,
                    properties=edge.properties,
                    created_at=datetime.now(timezone.utc),
                )
            )
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=EventType.GRAPH_RELATION_CREATED,
                    case_id=edge.case_id,
                    message=f"Graph edge {edge.relation.value}",
                    payload={
                        "from": str(edge.from_node_id),
                        "to": str(edge.to_node_id),
                        "relation": edge.relation.value,
                    },
                    actor="knowledge_graph",
                )
            )
        return edge

    def nodes_by_type(self, case_id: UUID, node_type: NodeType, limit: int = 100) -> list[GraphNode]:
        with get_session() as session:
            rows = (
                session.query(GraphNodeRow)
                .filter(GraphNodeRow.case_id == case_id, GraphNodeRow.node_type == node_type.value)
                .limit(limit)
                .all()
            )
            return [self._node(r) for r in rows]

    def neighbors(self, node_id: UUID, relation: RelationType | None = None, limit: int = 100) -> list[tuple[GraphEdge, GraphNode]]:
        with get_session() as session:
            q = session.query(GraphEdgeRow).filter(
                (GraphEdgeRow.from_node_id == node_id) | (GraphEdgeRow.to_node_id == node_id)
            )
            if relation:
                q = q.filter(GraphEdgeRow.relation == relation.value)
            edges = q.limit(limit).all()
            result: list[tuple[GraphEdge, GraphNode]] = []
            for e in edges:
                other_id = e.to_node_id if e.from_node_id == node_id else e.from_node_id
                n = session.query(GraphNodeRow).filter(GraphNodeRow.id == other_id).first()
                if n:
                    result.append((self._edge(e), self._node(n)))
            return result

    def evidence_supporting_finding(self, finding_node_id: UUID) -> list[GraphNode]:
        """All evidence nodes connected via SUPPORTS to a finding node."""
        out: list[GraphNode] = []
        for _edge, node in self.neighbors(finding_node_id, RelationType.SUPPORTS):
            if node.node_type == NodeType.EVIDENCE:
                out.append(node)
        # Also reverse direction: evidence -SUPPORTS-> finding
        with get_session() as session:
            edges = (
                session.query(GraphEdgeRow)
                .filter(
                    GraphEdgeRow.to_node_id == finding_node_id,
                    GraphEdgeRow.relation == RelationType.SUPPORTS.value,
                )
                .all()
            )
            for e in edges:
                n = session.query(GraphNodeRow).filter(GraphNodeRow.id == e.from_node_id).first()
                if n and n.node_type == NodeType.EVIDENCE:
                    out.append(self._node(n))
        return out

    def findings_for_artifact(self, artifact_node_id: UUID) -> list[GraphNode]:
        findings: list[GraphNode] = []
        for _edge, node in self.neighbors(artifact_node_id):
            if node.node_type == NodeType.FINDING:
                findings.append(node)
            if node.node_type == NodeType.OBSERVATION:
                for _e2, n2 in self.neighbors(node.id, RelationType.PRODUCED):
                    if n2.node_type == NodeType.FINDING:
                        findings.append(n2)
        return findings

    def observations_by_capability(self, case_id: UUID, capability: str) -> list[GraphNode]:
        nodes = self.nodes_by_type(case_id, NodeType.OBSERVATION)
        return [n for n in nodes if n.properties.get("capability") == capability]

    @staticmethod
    def _node(row: GraphNodeRow) -> GraphNode:
        return GraphNode(
            id=row.id,
            case_id=row.case_id,
            node_type=NodeType(row.node_type),
            label=row.label or "",
            ref_id=row.ref_id,
            properties=row.properties or {},
        )

    @staticmethod
    def _edge(row: GraphEdgeRow) -> GraphEdge:
        return GraphEdge(
            id=row.id,
            case_id=row.case_id,
            relation=RelationType(row.relation),
            from_node_id=row.from_node_id,
            to_node_id=row.to_node_id,
            properties=row.properties or {},
        )
