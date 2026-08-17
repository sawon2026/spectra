"""Case lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from spectra.core.db import CaseRow, ScopeRow, get_session
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.case import Case, CaseCreate, CaseStatus
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import AuthStatus, NetworkProfile, Scope, ScopeAsset, ScopeCreate

logger = get_logger(__name__)


class CaseService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus or EventBus()

    def create(self, data: CaseCreate) -> Case:
        case = Case(
            name=data.name,
            description=data.description,
            project_id=data.project_id,
            tags=data.tags,
            status=CaseStatus.DRAFT,
        )
        with get_session() as session:
            # uniqueness check
            existing = session.query(CaseRow).filter(CaseRow.name == case.name).first()
            if existing:
                raise ValueError(f"Case with name '{case.name}' already exists")
            row = CaseRow(
                id=case.id,
                name=case.name,
                description=case.description,
                status=case.status.value,
                project_id=case.project_id,
                tags=case.tags,
                created_at=case.created_at,
                updated_at=case.updated_at,
                closed_at=case.closed_at,
                metadata_=case.metadata,
            )
            session.add(row)
        self._bus.publish(
            SpectraEvent(
                event_type=EventType.CASE_CREATED,
                case_id=case.id,
                message=f"Case '{case.name}' created",
                payload={"name": case.name},
                actor="case_service",
            )
        )
        logger.info("case_created", case_id=str(case.id), name=case.name)
        return case

    def get(self, case_id: UUID) -> Case | None:
        with get_session() as session:
            row = session.query(CaseRow).filter(CaseRow.id == case_id).first()
            if not row:
                return None
            return self._to_model(row)

    def get_by_name(self, name: str) -> Case | None:
        with get_session() as session:
            row = session.query(CaseRow).filter(CaseRow.name == name).first()
            if not row:
                return None
            return self._to_model(row)

    def list_cases(
        self,
        status: CaseStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Case]:
        with get_session() as session:
            q = session.query(CaseRow).order_by(CaseRow.created_at.desc())
            if status:
                q = q.filter(CaseRow.status == status.value)
            rows = q.offset(max(0, offset)).limit(limit).all()
            return [self._to_model(r) for r in rows]

    def update_status(self, case_id: UUID, status: CaseStatus) -> Case:
        with get_session() as session:
            row = session.query(CaseRow).filter(CaseRow.id == case_id).first()
            if not row:
                raise ValueError(f"Case {case_id} not found")
            row.status = status.value
            row.updated_at = datetime.now(UTC)
            if status == CaseStatus.CLOSED:
                row.closed_at = datetime.now(UTC)
            session.flush()
            case = self._to_model(row)
        self._bus.publish(
            SpectraEvent(
                event_type=EventType.CASE_UPDATED,
                case_id=case_id,
                message=f"Status changed to {status.value}",
                payload={"status": status.value},
                actor="case_service",
            )
        )
        return case

    def set_scope(self, data: ScopeCreate) -> Scope:
        scope = Scope(
            case_id=data.case_id,
            auth_status=data.auth_status,
            auth_basis=data.auth_basis,
            auth_evidence=data.auth_evidence,
            in_scope_assets=data.in_scope_assets,
            out_of_scope_assets=data.out_of_scope_assets,
            allowed_activities=data.allowed_activities,
            forbidden_activities=data.forbidden_activities,
            network_profile=data.network_profile,
            time_window_start=data.time_window_start,
            time_window_end=data.time_window_end,
            notes=data.notes,
            ready_for_act=False,
        )
        # Auto-set ready only when fully authorized and assets present or offline
        if (
            scope.auth_status == AuthStatus.GRANTED
            and (scope.in_scope_assets or scope.network_profile == NetworkProfile.OFFLINE)
        ):
            scope.ready_for_act = True

        with get_session() as session:
            # replace existing scope for case
            session.query(ScopeRow).filter(ScopeRow.case_id == data.case_id).delete()
            row = ScopeRow(
                id=scope.id,
                case_id=scope.case_id,
                auth_status=scope.auth_status.value,
                auth_basis=scope.auth_basis,
                auth_evidence=scope.auth_evidence,
                in_scope_assets=[a.model_dump() for a in scope.in_scope_assets],
                out_of_scope_assets=[a.model_dump() for a in scope.out_of_scope_assets],
                allowed_activities=scope.allowed_activities,
                forbidden_activities=scope.forbidden_activities,
                network_profile=scope.network_profile.value,
                time_window_start=scope.time_window_start,
                time_window_end=scope.time_window_end,
                ready_for_act=scope.ready_for_act,
                notes=scope.notes,
                created_at=scope.created_at,
                updated_at=scope.updated_at,
            )
            session.add(row)

        self._bus.publish(
            SpectraEvent(
                event_type=EventType.SCOPE_UPDATED,
                case_id=scope.case_id,
                message=f"Scope set auth={scope.auth_status.value} net={scope.network_profile.value}",
                payload={
                    "auth_status": scope.auth_status.value,
                    "network_profile": scope.network_profile.value,
                    "ready_for_act": scope.ready_for_act,
                },
                actor="case_service",
            )
        )
        logger.info(
            "scope_set",
            case_id=str(scope.case_id),
            auth=scope.auth_status.value,
            ready=scope.ready_for_act,
        )
        return scope

    def get_scope(self, case_id: UUID) -> Scope | None:
        with get_session() as session:
            row = session.query(ScopeRow).filter(ScopeRow.case_id == case_id).first()
            if not row:
                return None
            return self._scope_from_row(row)

    def _scope_from_row(self, row: ScopeRow) -> Scope:
        def _assets(raw):
            out = []
            for a in raw or []:
                if isinstance(a, dict):
                    try:
                        out.append(ScopeAsset(**a))
                    except Exception:
                        pass
            return out

        return Scope(
            id=row.id,
            case_id=row.case_id,
            auth_status=AuthStatus(row.auth_status),
            auth_basis=row.auth_basis or "",
            auth_evidence=list(row.auth_evidence or []),
            in_scope_assets=_assets(row.in_scope_assets),
            out_of_scope_assets=_assets(row.out_of_scope_assets),
            allowed_activities=list(row.allowed_activities or []),
            forbidden_activities=list(row.forbidden_activities or []),
            network_profile=NetworkProfile(row.network_profile),
            time_window_start=row.time_window_start,
            time_window_end=row.time_window_end,
            ready_for_act=bool(row.ready_for_act),
            notes=row.notes or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_model(self, row: CaseRow) -> Case:
        return Case(
            id=row.id,
            name=row.name,
            description=row.description or "",
            status=CaseStatus(row.status),
            project_id=row.project_id,
            tags=list(row.tags or []),
            created_at=row.created_at,
            updated_at=row.updated_at,
            closed_at=row.closed_at,
            metadata=dict(row.metadata_ or {}),
        )
