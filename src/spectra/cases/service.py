"""Case lifecycle management."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from spectra.core.db import CaseRow, ScopeRow, get_session, session_scope
from spectra.models.case import Case, CaseStatus
from spectra.models.scope import Scope, ScopeStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseService:
    """CRUD and lifecycle for investigation cases."""

    def create(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Case:
        case_id = str(uuid4())
        now = _utcnow()
        with get_session() as session:
            row = CaseRow(
                id=case_id,
                name=name,
                description=description,
                status=CaseStatus.OPEN.value,
                created_at=now,
                updated_at=now,
                metadata_=metadata or {},
            )
            session.add(row)
            session.flush()
            return self._to_model(row)

    def get(self, case_id: str) -> Case | None:
        with get_session() as session:
            row = session.get(CaseRow, case_id)
            if row is None:
                return None
            return self._to_model(row)

    def list(self, limit: int = 100) -> list[Case]:
        with get_session() as session:
            rows = session.query(CaseRow).order_by(CaseRow.created_at.desc()).limit(limit).all()
            return [self._to_model(r) for r in rows]

    def update_status(self, case_id: str, status: CaseStatus | str) -> Case | None:
        status_val = status.value if isinstance(status, CaseStatus) else status
        with get_session() as session:
            row = session.get(CaseRow, case_id)
            if row is None:
                return None
            row.status = status_val
            row.updated_at = _utcnow()
            session.flush()
            return self._to_model(row)

    def set_scope(
        self,
        case_id: str,
        authorized_targets: list[str] | None = None,
        authorized_actions: list[str] | None = None,
        notes: str | None = None,
        status: ScopeStatus | str = ScopeStatus.PENDING,
    ) -> Scope | None:
        status_val = status.value if isinstance(status, ScopeStatus) else status
        with get_session() as session:
            case = session.get(CaseRow, case_id)
            if case is None:
                return None
            existing = (
                session.query(ScopeRow).filter(ScopeRow.case_id == case_id).order_by(ScopeRow.created_at.desc()).first()
            )
            now = _utcnow()
            if existing:
                existing.status = status_val
                if authorized_targets is not None:
                    existing.authorized_targets = authorized_targets
                if authorized_actions is not None:
                    existing.authorized_actions = authorized_actions
                if notes is not None:
                    existing.notes = notes
                existing.updated_at = now
                session.flush()
                return self._scope_to_model(existing)
            scope_id = str(uuid4())
            row = ScopeRow(
                id=scope_id,
                case_id=case_id,
                status=status_val,
                authorized_targets=authorized_targets or [],
                authorized_actions=authorized_actions or [],
                notes=notes,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return self._scope_to_model(row)

    def get_scope(self, case_id: str) -> Scope | None:
        with get_session() as session:
            row = (
                session.query(ScopeRow).filter(ScopeRow.case_id == case_id).order_by(ScopeRow.created_at.desc()).first()
            )
            if row is None:
                return None
            return self._scope_to_model(row)

    def _to_model(self, row: CaseRow) -> Case:
        return Case(
            id=row.id,
            name=row.name,
            description=row.description,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=row.metadata_ or {},
        )

    def _scope_to_model(self, row: ScopeRow) -> Scope:
        return Scope(
            id=row.id,
            case_id=row.case_id,
            status=row.status,
            authorized_targets=row.authorized_targets or [],
            authorized_actions=row.authorized_actions or [],
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
