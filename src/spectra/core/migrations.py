"""Schema versioning and non-destructive migration steps.

SQLite remains the default offline store. Migrations are additive:
create_all + stamped schema_version rows. Full Alembic can wrap these
steps later; rollback is not automatic and may be unsupported for
additive-only changes.

Honest limitations:
- No automatic destructive downgrade
- Existing DBs keep data; new tables/columns applied via create_all
- Operators should backup before major upgrades
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, text

from spectra.core.db import Base, get_session, init_db
from spectra.core.logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 13  # Phase 13 production hardening


class SchemaVersionRow(Base):
    __tablename__ = "schema_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    description = Column(String(256), default="")
    applied_at = Column(DateTime(timezone=True), nullable=False)


def _stamp(session, version: int, description: str) -> None:
    session.add(
        SchemaVersionRow(
            version=version,
            description=description,
            applied_at=datetime.now(UTC),
        )
    )


def _upgrade_to_13(session) -> None:
    """Additive Phase 13 objects — create_all handles new tables."""
    with suppress(Exception):
        session.execute(text("SELECT 1 FROM execution_ledger LIMIT 1"))
    logger.info("migration_step_applied", version=13, description="execution-ledger-audit")


MIGRATION_STEPS: dict[int, tuple[str, object]] = {
    13: ("phase13-execution-ledger-audit", _upgrade_to_13),
}


def ensure_schema(settings=None) -> int:
    """Apply idempotent create_all and record schema versions up to SCHEMA_VERSION."""
    init_db(settings)
    from spectra.core import db as _db  # noqa: F401

    with get_session() as session:
        try:
            row = session.query(SchemaVersionRow).order_by(SchemaVersionRow.id.desc()).first()
        except Exception:
            row = None
        current = int(row.version) if row is not None else 0

        if current == 0:
            _stamp(session, SCHEMA_VERSION, "phase13-baseline")
            logger.info("schema_version_recorded", version=SCHEMA_VERSION)
            return SCHEMA_VERSION

        if current < SCHEMA_VERSION:
            for ver in range(current + 1, SCHEMA_VERSION + 1):
                if ver in MIGRATION_STEPS:
                    desc, fn = MIGRATION_STEPS[ver]
                    try:
                        fn(session)  # type: ignore[operator]
                    except Exception as exc:
                        logger.warning("migration_step_warn", version=ver, error=str(exc))
                    _stamp(session, ver, desc)
                    logger.info("schema_version_recorded", version=ver, description=desc)
            return SCHEMA_VERSION

        return current


def current_schema_version() -> int | None:
    try:
        with get_session() as session:
            row = session.query(SchemaVersionRow).order_by(SchemaVersionRow.id.desc()).first()
            return int(row.version) if row else None
    except Exception:
        return None


def migration_notes() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "sqlite+create_all",
        "alembic": "optional future wrapper; not required for offline path",
        "rollback": "not automatic; restore from backup",
        "steps": {str(k): v[0] for k, v in MIGRATION_STEPS.items()},
    }
