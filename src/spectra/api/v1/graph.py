"""Knowledge graph read API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from spectra.api.deps import Principal, get_principal, get_services
from spectra.api.schemas.resources import GraphEdgeOut, GraphNodeOut
from spectra.core.db import GraphEdgeRow, GraphNodeRow, get_session

router = APIRouter()


@router.get("/nodes/{case_id}", response_model=list[GraphNodeOut])
def list_nodes(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[GraphNodeOut]:
    get_services()
    with get_session() as session:
        rows = session.query(GraphNodeRow).filter(GraphNodeRow.case_id == case_id).limit(500).all()
        return [
            GraphNodeOut(
                id=UUID(str(r.id)),
                case_id=UUID(str(r.case_id)) if r.case_id else None,
                node_type=str(r.node_type or ""),
                label=str(r.label or ""),
            )
            for r in rows
        ]


@router.get("/edges/{case_id}", response_model=list[GraphEdgeOut])
def list_edges(case_id: UUID, principal: Principal = Depends(get_principal)) -> list[GraphEdgeOut]:
    get_services()
    with get_session() as session:
        rows = session.query(GraphEdgeRow).filter(GraphEdgeRow.case_id == case_id).limit(1000).all()
        return [
            GraphEdgeOut(
                id=UUID(str(r.id)),
                relation=str(r.relation or ""),
                from_node_id=UUID(str(r.from_node_id)),
                to_node_id=UUID(str(r.to_node_id)),
            )
            for r in rows
        ]
