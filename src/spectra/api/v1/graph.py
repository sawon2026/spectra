"""Knowledge graph read API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from spectra.api.deps import Principal, get_principal, get_services
from spectra.api.schemas.resources import GraphEdgeOut, GraphNodeOut
from spectra.core.db import GraphEdgeRow, GraphNodeRow, get_session

router = APIRouter()


@router.get("/nodes/{case_id}", response_model=list[GraphNodeOut])
def list_nodes(
    case_id: UUID,
    principal: Principal = Depends(get_principal),
    node_type: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Label search"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[GraphNodeOut]:
    get_services()
    with get_session() as session:
        query = session.query(GraphNodeRow).filter(GraphNodeRow.case_id == case_id)
        if node_type:
            query = query.filter(GraphNodeRow.node_type == node_type)
        if q:
            query = query.filter(GraphNodeRow.label.ilike(f"%{q}%"))
        rows = query.limit(limit).all()
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
def list_edges(
    case_id: UUID,
    principal: Principal = Depends(get_principal),
    relation: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[GraphEdgeOut]:
    get_services()
    with get_session() as session:
        query = session.query(GraphEdgeRow).filter(GraphEdgeRow.case_id == case_id)
        if relation:
            query = query.filter(GraphEdgeRow.relation == relation)
        rows = query.limit(limit).all()
        return [
            GraphEdgeOut(
                id=UUID(str(r.id)),
                relation=str(r.relation or ""),
                from_node_id=UUID(str(r.from_node_id)),
                to_node_id=UUID(str(r.to_node_id)),
            )
            for r in rows
        ]
