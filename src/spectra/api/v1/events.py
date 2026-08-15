"""Server-Sent Events — EventBus hub with optional DB replay.

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
from spectra.events.sse import get_sse_hub

router = APIRouter()


async def _live_stream(
    request: Request,
    case_id: UUID | None,
    last_event_id: str | None,
) -> AsyncIterator[str]:
    hub = get_sse_hub()
    client = hub.register(case_id=case_id, last_event_id=last_event_id)
    try:
        yield f"event: connected\ndata: {json.dumps({'client_id': str(client.id)})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(client.queue.get(), timeout=15.0)
                yield f"event: spectra\ndata: {json.dumps(data)}\n\n"
            except TimeoutError:
                yield f"event: ping\ndata: {json.dumps({'ok': True})}\n\n"
    finally:
        hub.unregister(client.id)


@router.get("/stream")
async def stream_events(
    request: Request,
    case_id: UUID | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    get_services()  # ensure EventBus + hub wired
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
    return {"clients": hub.client_count, "mode": "eventbus-sse"}
