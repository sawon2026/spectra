"""SQLite database layer with safe defaults."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from spectra.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class CaseRow(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(64), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class ScopeRow(Base):
    __tablename__ = "scopes"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    status = Column(String(64), nullable=False, default="pending")
    authorized_targets = Column(JSON, default=list)
    authorized_actions = Column(JSON, default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=True)
    sha256 = Column(String(64), nullable=False, index=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    storage_path = Column(String(1024), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class FindingRow(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(32), nullable=False, default="info")
    category = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(128), nullable=True)
    evidence_ids = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class EventRow(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    event_type = Column(String(128), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class CapabilityRow(Base):
    __tablename__ = "capabilities"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    risk_level = Column(String(32), nullable=False, default="low")
    requires_scope = Column(Boolean, nullable=False, default=True)
    enabled = Column(Boolean, nullable=False, default=True)
    adapter_class = Column(String(512), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    status = Column(String(64), nullable=False, default="active")
    current_phase = Column(String(128), nullable=True)
    state = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ObservationRow(Base):
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    observation_type = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class GraphNodeRow(Base):
    __tablename__ = "graph_nodes"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    node_type = Column(String(128), nullable=False)
    label = Column(String(512), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    edge_type = Column(String(128), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class MemoryEntryRow(Base):
    __tablename__ = "memory_entries"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    key = Column(String(512), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    features = Column(JSON, default=list)  # for deterministic similarity
    metadata_ = Column("metadata", JSON, default=dict)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args, future=True)

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):  # noqa: ARG001
            if url.startswith("sqlite"):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def init_db() -> None:
    """Create all tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_scope() -> Session:
    """Return a new session (caller must close)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal()
