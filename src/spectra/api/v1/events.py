"""Server-Sent Events — EventBus hub + DB-backed replay for multi-worker.

Never emits secrets. Works across workers via SQLite EventRow polling.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from spectra.api.deps import Principal, get_principal, get_services
from spectra.core.db import EventRow, get_session
from spectra.events.sse import get_sse_hub, sanitize_payload

router = APIRouter()


def _row_to_dict(row: EventRow) -> dict:
    return {
        "id": str(row.id),
        "event_type": row.event_type or "audit",
        "case_id": str(row.case_id) if row.case_id else None,
        "message": (row.message or "")[:500],
        "payload": sanitize_payload(dict(row.payload or {})),
        "actor": row.actor or "system",
        "created_at": row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
    }


def _fetch_new_events(case_id: UUID | None, after_id: str | None, limit: int = 20) -> list[dict]:
    with get_session() as session:
        q = session.query(EventRow).order_by(EventRow.created_at.asc())
        if case_id:
            q = q.filter(EventRow.case_id == case_id)
        rows = q.limit(500).all()
        out: list[dict] = []
        seen = after_id is None
        for r in rows:
            rid = str(r.id)
            if not seen:
                if rid == after_id:
                    seen = True
                continue
            out.append(_row_to_dict(r))
            if len(out) >= limit:
                break
        return out


async def _live_stream(
    request: Request,
    case_id: UUID | None,
    last_event_id: str | None,
) -> AsyncIterator[str]:
    hub = get_sse_hub()
    client = hub.register(case_id=case_id, last_event_id=last_event_id)
    cursor = last_event_id
    try:
        yield f"event: connected\ndata: {json.dumps({'client_id': str(client.id), 'mode': 'hub+db'})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(client.queue.get(), timeout=2.0)
                cursor = data.get("id") or cursor
                yield f"event: spectra\ndata: {json.dumps(data)}\n\n"
                continue
            except TimeoutError:
                pass
            try:
                batch = await asyncio.to_thread(_fetch_new_events, case_id, cursor, 10)
                for data in batch:
                    cursor = data.get("id") or cursor
                    yield f"event: spectra\ndata: {json.dumps(data)}\n\n"
                if not batch:
                    yield f"event: ping\ndata: {json.dumps({'ok': True})}\n\n"
            except Exception:
                yield f"event: ping\ndata: {json.dumps({'ok': True})}\n\n"
            await asyncio.sleep(1.0)
    finally:
        hub.unregister(client.id)


@router.get("/stream")
async def stream_events(
    request: Request,
    case_id: UUID | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    get_services()
    return StreamingResponse(
        _live_stream(request, case_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/hub-status")
def hub_status(principal: Principal = Depends(get_principal)) -> dict:
    hub = get_sse_hub()
    return {"clients": hub.client_count, "mode": "hub+db", "multi_worker": "db-poll"}
