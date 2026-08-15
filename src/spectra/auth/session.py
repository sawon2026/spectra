"""Persistent session/token authentication — offline-first, no plaintext passwords.

Auth answers: who is the user?
PolicyEngine answers: is this capability execution allowed?
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from spectra.core.db import SessionRow, get_session


class Role(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class Permission(str, Enum):
    CASE_READ = "case.read"
    CASE_WRITE = "case.write"
    INVESTIGATION_READ = "investigation.read"
    INVESTIGATION_CONTROL = "investigation.control"
    EVIDENCE_READ = "evidence.read"
    FINDING_WRITE = "finding.write"
    REPORT_EXPORT = "report.export"
    PLUGIN_MANAGE = "plugin.manage"
    PROVIDER_MANAGE = "provider.manage"
    SYSTEM_ADMIN = "system.admin"
    AUDIT_READ = "audit.read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RESEARCHER: frozenset(
        {
            Permission.CASE_READ,
            Permission.CASE_WRITE,
            Permission.INVESTIGATION_READ,
            Permission.INVESTIGATION_CONTROL,
            Permission.EVIDENCE_READ,
            Permission.FINDING_WRITE,
            Permission.REPORT_EXPORT,
            Permission.AUDIT_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.CASE_READ,
            Permission.INVESTIGATION_READ,
            Permission.EVIDENCE_READ,
            Permission.REPORT_EXPORT,
            Permission.AUDIT_READ,
        }
    ),
}


@dataclass
class SessionInfo:
    session_id: UUID
    subject: str
    role: Role
    token_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    offline: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def has(self, perm: Permission) -> bool:
        return perm in ROLE_PERMISSIONS.get(self.role, frozenset())

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


def _hash_token(token: str, salt: str = "spectra-v1") -> str:
    return hmac.new(salt.encode(), token.encode(), hashlib.sha256).hexdigest()


class AuthService:
    """SQLite-backed session store with optional static API token.

    Never stores plaintext tokens — only HMAC hashes.
    Offline mode: if SPECTRA_API_TOKEN is unset, local principal is allowed.
    """

    def __init__(self) -> None:
        self._static_hash: str | None = None
        static = os.environ.get("SPECTRA_API_TOKEN")
        if static:
            self._static_hash = _hash_token(static)

    def create_session(
        self,
        subject: str,
        role: Role = Role.RESEARCHER,
        ttl_hours: int = 24,
    ) -> tuple[str, SessionInfo]:
        token = secrets.token_urlsafe(32)
        th = _hash_token(token)
        now = datetime.now(UTC)
        session = SessionInfo(
            session_id=uuid4(),
            subject=subject,
            role=role,
            token_hash=th,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            offline=not bool(self._static_hash),
        )
        with get_session() as db:
            db.add(
                SessionRow(
                    id=session.session_id,
                    subject=session.subject,
                    role=session.role.value,
                    token_hash=th,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                    revoked_at=None,
                    last_seen_at=now,
                    offline=session.offline,
                    metadata_json={},
                )
            )
        return token, session

    def resolve(self, bearer: str | None, role_hint: str | None = None) -> SessionInfo | None:
        if bearer:
            th = _hash_token(bearer)
            if self._static_hash and hmac.compare_digest(th, self._static_hash):
                role = Role.RESEARCHER
                if role_hint in {r.value for r in Role}:
                    role = Role(role_hint)
                return SessionInfo(
                    session_id=uuid4(),
                    subject="api-token",
                    role=role,
                    token_hash=th,
                    offline=False,
                )
            with get_session() as db:
                row = db.query(SessionRow).filter(SessionRow.token_hash == th).first()
                if not row:
                    return None
                if row.revoked_at is not None:
                    return None
                expires = row.expires_at
                if expires is not None:
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=UTC)
                    if datetime.now(UTC) > expires:
                        return None
                try:
                    role = Role(str(row.role))
                except ValueError:
                    role = Role.VIEWER
                row.last_seen_at = datetime.now(UTC)  # type: ignore[assignment]
                return SessionInfo(
                    session_id=UUID(str(row.id)),
                    subject=str(row.subject),
                    role=role,
                    token_hash=str(row.token_hash),
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                    offline=bool(row.offline),
                    metadata=dict(row.metadata_json or {}),
                )
        if self._static_hash:
            return None
        role = Role.ADMIN
        if role_hint in {r.value for r in Role}:
            role = Role(role_hint)
        return SessionInfo(
            session_id=uuid4(),
            subject="local",
            role=role,
            token_hash="",
            offline=True,
        )

    def revoke(self, bearer: str) -> bool:
        th = _hash_token(bearer)
        with get_session() as db:
            row = db.query(SessionRow).filter(SessionRow.token_hash == th).first()
            if not row:
                return False
            row.revoked_at = datetime.now(UTC)  # type: ignore[assignment]
            return True

    def revoke_session(self, session_id: UUID) -> bool:
        with get_session() as db:
            row = db.query(SessionRow).filter(SessionRow.id == session_id).first()
            if not row:
                return False
            row.revoked_at = datetime.now(UTC)  # type: ignore[assignment]
            return True


_auth: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth
    if _auth is None:
        _auth = AuthService()
    return _auth


def reset_auth_service() -> None:
    global _auth
    _auth = None
