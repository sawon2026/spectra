"""Authentication and roles — separate from PolicyEngine execution gate."""

from spectra.auth.session import AuthService, Permission, Role, SessionInfo

__all__ = ["AuthService", "Permission", "Role", "SessionInfo"]
