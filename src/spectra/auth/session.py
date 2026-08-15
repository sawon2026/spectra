"""Session/token authentication — offline-first, no plaintext passwords.

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
    """In-memory session store with optional static API token.

    Offline mode: if SPECTRA_API_TOKEN is unset, local admin principal is allowed.
    Never stores plaintext tokens — only HMAC hashes.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionInfo] = {}
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
        session = SessionInfo(
            session_id=uuid4(),
            subject=subject,
            role=role,
            token_hash=th,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
            offline=not bool(self._static_hash),
        )
        self._sessions[th] = session
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
            sess = self._sessions.get(th)
            if sess and not sess.is_expired():
                return sess
            return None
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
        return self._sessions.pop(th, None) is not None


_auth: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth
    if _auth is None:
        _auth = AuthService()
    return _auth


def reset_auth_service() -> None:
    global _auth
    _auth = None
