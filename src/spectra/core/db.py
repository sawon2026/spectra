"""SQLite database layer with safe defaults."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import CHAR, TypeDecorator

from spectra.core.config import SpectraSettings, get_settings
from spectra.core.logging import get_logger

logger = get_logger(__name__)


class GUID(TypeDecorator):
    """Platform-independent GUID type stored as CHAR(36)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "sqlite":
            return dialect.type_descriptor(CHAR(36))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return value
        return UUID(str(value))


class Base(DeclarativeBase):
    pass


class CaseRow(Base):
    __tablename__ = "cases"

    id = Column(GUID(), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, default="")
    status = Column(String(32), nullable=False, default="draft")
    project_id = Column(String(64), nullable=True)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)


class ScopeRow(Base):
    __tablename__ = "scopes"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    auth_status = Column(String(32), nullable=False, default="pending")
    auth_basis = Column(String(256), default="")
    auth_evidence = Column(Text, default="")
    in_scope_assets = Column(JSON, default=list)
    out_of_scope_assets = Column(JSON, default=list)
    allowed_activities = Column(JSON, default=list)
    forbidden_activities = Column(JSON, default=list)
    network_profile = Column(String(64), nullable=False, default="offline")
    time_window_start = Column(DateTime(timezone=True), nullable=True)
    time_window_end = Column(DateTime(timezone=True), nullable=True)
    ready_for_act = Column(Boolean, default=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    source_type = Column(String(32), nullable=False)
    content_hash = Column(String(128), nullable=True)
    raw_excerpt = Column(Text, default="")
    file_path = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class FindingRow(Base):
    __tablename__ = "findings"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    severity = Column(String(32), nullable=False, default="info")
    status = Column(String(32), nullable=False, default="open")
    confidence = Column(Float, default=0.5)
    evidence_quality = Column(Float, default=0.5)
    evidence_ids = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EventRow(Base):
    __tablename__ = "events"

    id = Column(GUID(), primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    case_id = Column(GUID(), nullable=True, index=True)
    message = Column(Text, default="")
    payload = Column(JSON, default=dict)
    actor = Column(String(128), default="system")
    created_at = Column(DateTime(timezone=True), nullable=False)


class CapabilityRow(Base):
    __tablename__ = "capabilities"

    id = Column(GUID(), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    category = Column(String(64), nullable=False)
    risk_level = Column(String(32), nullable=False, default="low")
    requires_authorization = Column(Boolean, default=True)
    description = Column(Text, default="")
    health_status = Column(String(32), default="unknown")
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


_engine = None
_SessionLocal = None


def init_db(settings: SpectraSettings | None = None) -> None:
    global _engine, _SessionLocal
    settings = settings or get_settings()
    settings.ensure_data_dir()
    url = settings.get_database_url()
    _engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        if url.startswith("sqlite"):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    logger.info("database_initialized", url=url)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_for_tests(settings: SpectraSettings | None = None) -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        Base.metadata.drop_all(_engine)
        _engine.dispose()
    init_db(settings)


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    task_id = Column(GUID(), nullable=True)
    status = Column(String(32), nullable=False, default="created", index=True)
    target = Column(Text, default="")
    objectives = Column(JSON, default=list)
    hypotheses = Column(JSON, default=list)
    current_plan = Column(JSON, default=list)
    completed_steps = Column(JSON, default=list)
    pending_steps = Column(JSON, default=list)
    failed_steps = Column(JSON, default=list)
    blocked_steps = Column(JSON, default=list)
    observation_ids = Column(JSON, default=list)
    evidence_refs = Column(JSON, default=list)
    planner_version = Column(String(64), default="deterministic-0.1")
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ObservationRow(Base):
    __tablename__ = "observations"

    id = Column(GUID(), primary_key=True)
    investigation_id = Column(GUID(), nullable=False, index=True)
    case_id = Column(GUID(), nullable=True, index=True)
    source = Column(String(64), default="executor")
    capability = Column(String(128), default="", index=True)
    status = Column(String(32), nullable=False, index=True)
    summary = Column(Text, default="")
    structured_data = Column(JSON, default=dict)
    evidence_refs = Column(JSON, default=list)
    confidence = Column(Float, default=1.0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class GraphNodeRow(Base):
    __tablename__ = "graph_nodes"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=True, index=True)
    node_type = Column(String(64), nullable=False, index=True)
    label = Column(String(512), default="")
    ref_id = Column(GUID(), nullable=True, index=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=True, index=True)
    relation = Column(String(64), nullable=False, index=True)
    from_node_id = Column(GUID(), nullable=False, index=True)
    to_node_id = Column(GUID(), nullable=False, index=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class MemoryEntryRow(Base):
    __tablename__ = "case_memory"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, default="")
    tags = Column(JSON, default=list)
    features = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class WorkflowRow(Base):
    """Durable investigation workflow (Phase 6)."""

    __tablename__ = "workflows"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    investigation_id = Column(GUID(), nullable=True, index=True)
    task_id = Column(GUID(), nullable=True)
    status = Column(String(32), nullable=False, default="created", index=True)
    goal_json = Column(JSON, default=dict)
    decision_history = Column(JSON, default=list)
    observation_ids = Column(JSON, default=list)
    evidence_refs = Column(JSON, default=list)
    finding_ids = Column(JSON, default=list)
    plan_revisions = Column(JSON, default=list)
    retries = Column(JSON, default=dict)
    last_step_id = Column(GUID(), nullable=True)
    last_execution_token = Column(String(64), nullable=True)
    recovery_notes = Column(Text, default="")
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class TimelineEntryRow(Base):
    """Unified investigation timeline (Phase 6)."""

    __tablename__ = "timeline_entries"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    investigation_id = Column(GUID(), nullable=True, index=True)
    workflow_id = Column(GUID(), nullable=True, index=True)
    kind = Column(String(32), nullable=False, index=True)
    source = Column(String(128), default="system")
    summary = Column(Text, default="")
    confidence = Column(Float, nullable=True)
    references = Column(JSON, default=list)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ProvenanceLinkRow(Base):
    """Evidence provenance chain edges (Phase 6)."""

    __tablename__ = "provenance_links"

    id = Column(GUID(), primary_key=True)
    case_id = Column(GUID(), nullable=False, index=True)
    from_kind = Column(String(32), nullable=False)
    from_id = Column(GUID(), nullable=False, index=True)
    to_kind = Column(String(32), nullable=False)
    to_id = Column(GUID(), nullable=False, index=True)
    relation = Column(String(64), nullable=False, default="produced")
    content_hash = Column(String(128), nullable=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
