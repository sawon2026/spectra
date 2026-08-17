"""Deterministic schema bootstrap and version stamp.

SQLite remains the default. Uses SQLAlchemy metadata.create_all (idempotent)
plus a schema_version row for operational visibility. Full Alembic can be
introduced later without changing the default offline path.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from spectra.core.db import Base, get_session, init_db
from spectra.core.logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 10  # Phase 10 baseline


class SchemaVersionRow(Base):
    __tablename__ = "schema_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    description = Column(String(256), default="")
    applied_at = Column(DateTime(timezone=True), nullable=False)


def ensure_schema(settings=None) -> int:
    """Apply idempotent create_all and record schema version if missing."""
    init_db(settings)
    with get_session() as session:
        try:
            row = session.query(SchemaVersionRow).order_by(SchemaVersionRow.id.desc()).first()
        except Exception:
            row = None
        if row is None:
            session.add(
                SchemaVersionRow(
                    version=SCHEMA_VERSION,
                    description="phase10-baseline",
                    applied_at=datetime.now(UTC),
                )
            )
            logger.info("schema_version_recorded", version=SCHEMA_VERSION)
            return SCHEMA_VERSION
        return int(row.version)


def current_schema_version() -> int | None:
    try:
        with get_session() as session:
            row = session.query(SchemaVersionRow).order_by(SchemaVersionRow.id.desc()).first()
            return int(row.version) if row else None
    except Exception:
        return None
