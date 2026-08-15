"""SSE connection manager — bridges EventBus to live web clients.

Keeps SQLite as durable history; in-memory queues for live push.
Never emits secrets.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from spectra.core.logging import get_logger
from spectra.models.events import SpectraEvent

logger = get_logger(__name__)

_FORBIDDEN_KEYS = frozenset(
    {"api_key", "token", "password", "secret", "authorization", "private_key", "bearer"}
)


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if k.lower() in _FORBIDDEN_KEYS:
            out[k] = "[redacted]"
        elif isinstance(v, str) and len(v) > 2000:
            out[k] = v[:2000] + "…"
        else:
            out[k] = v
    return out


def event_to_sse_dict(event: SpectraEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        "case_id": str(event.case_id) if event.case_id else None,
        "message": (event.message or "")[:500],
        "payload": sanitize_payload(dict(event.payload or {})),
        "actor": event.actor or "system",
        "created_at": event.created_at.isoformat() if event.created_at else datetime.now(UTC).isoformat(),
    }


@dataclass
class SSEClient:
    id: UUID = field(default_factory=uuid4)
    case_id: UUID | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    last_event_id: str | None = None


class SSEHub:
    """Fan-out EventBus events to connected SSE clients."""

    def __init__(self, max_buffer: int = 200) -> None:
        self._clients: dict[UUID, SSEClient] = {}
        self._recent: deque[dict[str, Any]] = deque(maxlen=max_buffer)
        self._by_case: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max_buffer))
        self._lock = asyncio.Lock()

    def on_event(self, event: SpectraEvent) -> None:
        """Synchronous EventBus handler — enqueue for all matching clients."""
        data = event_to_sse_dict(event)
        self._recent.append(data)
        if data.get("case_id"):
            self._by_case[str(data["case_id"])].append(data)
        dead: list[UUID] = []
        for cid, client in list(self._clients.items()):
            if client.case_id and data.get("case_id") and str(client.case_id) != data["case_id"]:
                continue
            try:
                client.queue.put_nowait(data)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self._clients.pop(cid, None)

    def register(self, case_id: UUID | None = None, last_event_id: str | None = None) -> SSEClient:
        client = SSEClient(case_id=case_id, last_event_id=last_event_id)
        self._clients[client.id] = client
        source = self._by_case[str(case_id)] if case_id else self._recent
        replay = list(source)
        if last_event_id:
            idx = next((i for i, e in enumerate(replay) if e.get("id") == last_event_id), None)
            if idx is not None:
                replay = replay[idx + 1 :]
            else:
                replay = []
        for item in replay:
            try:
                client.queue.put_nowait(item)
            except Exception:
                break
        logger.info("sse_client_registered", client_id=str(client.id), case_id=str(case_id) if case_id else None)
        return client

    def unregister(self, client_id: UUID) -> None:
        self._clients.pop(client_id, None)

    @property
    def client_count(self) -> int:
        return len(self._clients)


_hub: SSEHub | None = None


def get_sse_hub() -> SSEHub:
    global _hub
    if _hub is None:
        _hub = SSEHub()
    return _hub


def reset_sse_hub() -> None:
    global _hub
    _hub = None
