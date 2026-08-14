"""Policy and authorization engine — deterministic, never AI-overridable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from spectra.core.config import SpectraSettings, get_settings
from spectra.core.logging import get_logger
from spectra.models.scope import AuthStatus, NetworkProfile, Scope

logger = get_logger(__name__)


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    code: str = "ok"
    details: dict[str, Any] | None = None


class PolicyEngine:
    """Evaluates whether an activity is authorized for a given scope.

    This engine is intentionally deterministic and free of AI influence.
    """

    def __init__(self, settings: SpectraSettings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate(
        self,
        scope: Scope | None,
        activity: str,
        *,
        asset_identifier: str | None = None,
        network_required: bool = False,
        risk_level: str = "low",
        case_id: UUID | None = None,
    ) -> PolicyDecision:
        if not self.settings.require_scope_for_execution and not self.settings.policy_strict:
            # Explicit non-strict mode still requires scope when require_scope is True
            pass

        if scope is None:
            return PolicyDecision(
                allowed=False,
                reason="No scope defined for this case; authorization required before execution",
                code="no_scope",
            )

        if scope.auth_status != AuthStatus.GRANTED:
            return PolicyDecision(
                allowed=False,
                reason=f"Authorization status is '{scope.auth_status.value}', not 'granted'",
                code="auth_not_granted",
            )

        if not scope.ready_for_act:
            return PolicyDecision(
                allowed=False,
                reason="Scope is not ready_for_act (auth must be granted and status ready)",
                code="not_ready",
            )

        # Time window
        now = datetime.now(UTC)
        if scope.time_window_start and now < scope.time_window_start:
            return PolicyDecision(allowed=False, reason="Current time is before scope time window", code="before_window")
        if scope.time_window_end and now > scope.time_window_end:
            return PolicyDecision(allowed=False, reason="Current time is after scope time window", code="after_window")

        # Forbidden activities
        if activity in scope.forbidden_activities:
            return PolicyDecision(
                allowed=False,
                reason=f"Activity '{activity}' is explicitly forbidden in scope",
                code="forbidden",
            )

        # Allowed activities (if list non-empty, must be listed)
        if scope.allowed_activities and activity not in scope.allowed_activities:
            return PolicyDecision(
                allowed=False,
                reason=f"Activity '{activity}' is not in allowed_activities",
                code="not_allowed",
            )

        # Asset scope
        if asset_identifier and scope.in_scope_assets:
            ids = {a.identifier for a in scope.in_scope_assets}
            # Also check path basename match for convenience
            from pathlib import Path

            base = Path(asset_identifier).name
            if asset_identifier not in ids and base not in ids:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Asset '{asset_identifier}' is not in scope",
                    code="asset_out_of_scope",
                )

        # Network profile
        if network_required:
            if scope.network_profile == NetworkProfile.OFFLINE:
                return PolicyDecision(
                    allowed=False,
                    reason="Network required but scope network_profile is offline",
                    code="network_offline",
                )

        logger.info(
            "policy_allowed",
            activity=activity,
            case_id=str(case_id or scope.case_id),
            risk_level=risk_level,
        )
        return PolicyDecision(allowed=True, reason="Policy checks passed", code="ok")
