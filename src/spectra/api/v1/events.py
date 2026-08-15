"""Server-Sent Events stream for investigation timeline/events.

Never emits secrets, API keys, or raw credentials.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from spectra.api.deps import Principal, get_principal, get_services
from spectra.core.db import EventRow, get_session

router = APIRouter()

_SAFE_EVENT_TYPES = {
    "case.created",
    "scope.created",
    "scope.ready",
    "policy.check",
    "policy.denied",
    "tool.executed",
    "tool.failed",
    "evidence.recorded",
    "finding.created",
    "observation.created",
    "plan.created",
    "replan.triggered",
    "investigation.completed",
    "investigation.paused",
    "investigation.resumed",
    "investigation.failed",
    "goal.created",
    "capability.selected",
    "capability.blocked",
    "capability.executed",
    "audit",
}


def _sanitize_payload(payload: dict) -> dict:
    forbidden = {"api_key", "token", "password", "secret", "authorization", "private_key"}
    out = {}
    for k, v in (payload or {}).items():
        if k.lower() in forbidden:
            out[k] = "[redacted]"
        elif isinstance(v, str) and len(v) > 2000:
            out[k] = v[:2000] + "…"
        else:
            out[k] = v
    return out


async def _event_stream(case_id: UUID | None, request: Request) -> AsyncIterator[str]:
    last_seen: set[str] = set()
    while True:
        if await request.is_disconnected():
            break
        with get_session() as session:
            q = session.query(EventRow).order_by(EventRow.created_at.desc()).limit(50)
            if case_id:
                q = q.filter(EventRow.case_id == case_id)
            rows = list(reversed(q.all()))
        for row in rows:
            eid = str(row.id)
            if eid in last_seen:
                continue
            last_seen.add(eid)
            et = row.event_type or "audit"
            if et not in _SAFE_EVENT_TYPES and not et.startswith(("investigation.", "workflow.")):
                continue
            data = {
                "id": eid,
                "event_type": et,
                "case_id": str(row.case_id) if row.case_id else None,
                "message": (row.message or "")[:500],
                "payload": _sanitize_payload(dict(row.payload or {})),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            yield f"event: spectra\ndata: {json.dumps(data)}\n\n"
        await asyncio.sleep(1.0)


@router.get("/stream")
async def stream_events(
    request: Request,
    case_id: UUID | None = Query(default=None),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    get_services()  # ensure DB init
    return StreamingResponse(
        _event_stream(case_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
