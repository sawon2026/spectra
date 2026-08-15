"""Plugin management — list/enable/disable; never bypasses PolicyEngine."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from spectra.api.deps import Principal, ensure_write, get_principal, get_services
from spectra.core.db import PluginConfigRow, get_session
from spectra.plugins.base import PluginRegistry

router = APIRouter()

_VALID_STATES = {"available", "enabled", "disabled", "unavailable", "invalid"}


class PluginOut(BaseModel):
    name: str
    version: str = "0.1.0"
    state: str = "available"
    health: str = "unknown"
    category: str = ""


class PluginStateIn(BaseModel):
    state: str = Field(..., pattern="^(available|enabled|disabled|unavailable|invalid)$")


def _seed_from_registry() -> None:
    """Ensure known plugins appear in config table."""
    items: list = []
    try:
        reg = PluginRegistry()
        items = list(getattr(reg, "list", lambda: [])())
    except Exception:
        items = []
    defaults = [
        ("file-info", "0.1.0", "tool"),
        ("hash-compute", "0.1.0", "tool"),
        ("null-llm", "0.1.0", "ai_provider"),
    ]
    with get_session() as session:
        for name, ver, _cat in defaults:
            row = session.query(PluginConfigRow).filter(PluginConfigRow.name == name).first()
            if not row:
                session.add(
                    PluginConfigRow(
                        id=uuid4(),
                        name=name,
                        version=ver,
                        state="enabled",
                        health="healthy",
                        config_json={},
                        updated_at=datetime.now(UTC),
                    )
                )
        for item in items or []:
            raw_name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
            if not raw_name:
                continue
            pname = str(raw_name)
            row = session.query(PluginConfigRow).filter(PluginConfigRow.name == pname).first()
            if not row:
                session.add(
                    PluginConfigRow(
                        id=uuid4(),
                        name=pname,
                        version=str(getattr(item, "version", "0.1.0")),
                        state="available",
                        health="unknown",
                        config_json={},
                        updated_at=datetime.now(UTC),
                    )
                )


@router.get("", response_model=list[PluginOut])
def list_plugins(principal: Principal = Depends(get_principal)) -> list[PluginOut]:
    get_services()
    _seed_from_registry()
    with get_session() as session:
        rows = session.query(PluginConfigRow).order_by(PluginConfigRow.name).all()
        return [
            PluginOut(
                name=str(r.name),
                version=str(r.version or "0.1.0"),
                state=str(r.state or "available"),
                health=str(r.health or "unknown"),
            )
            for r in rows
        ]


@router.post("/{name}/state", response_model=PluginOut)
def set_plugin_state(
    name: str,
    body: PluginStateIn,
    principal: Principal = Depends(get_principal),
) -> PluginOut:
    ensure_write(principal)
    if principal.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    get_services()
    with get_session() as session:
        row = session.query(PluginConfigRow).filter(PluginConfigRow.name == name).first()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plugin not found")
        setattr(row, "state", body.state)
        setattr(row, "updated_at", datetime.now(UTC))
        return PluginOut(
            name=str(row.name),
            version=str(row.version or "0.1.0"),
            state=str(row.state),
            health=str(row.health or "unknown"),
        )
