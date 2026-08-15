"""Policy and authorization engine — deterministic, never AI-overridable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import AuthStatus, NetworkProfile, Scope

logger = get_logger(__name__)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    activity: str
    case_id: UUID | None = None
    details: dict[str, Any] | None = None


class PolicyEngine:
    """Hard gate for any potentially impactful action.

    AI planners may *request* actions; this engine alone decides whether
    they may proceed. Decisions are logged as audit events.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

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
        if scope is None:
            decision = PolicyDecision(
                allowed=False,
                reason="No scope defined for this case. Create and authorize a scope before acting.",
                activity=activity,
                case_id=case_id,
            )
            self._emit(decision)
            return decision

        if scope.auth_status != AuthStatus.GRANTED:
            decision = PolicyDecision(
                allowed=False,
                reason=f"Authorization status is '{scope.auth_status.value}', required 'granted'.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision

        if not scope.ready_for_act:
            decision = PolicyDecision(
                allowed=False,
                reason="Scope is not marked ready_for_act. Complete the authorization checklist.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision

        now = datetime.now(UTC)
        if scope.time_window_start and now < scope.time_window_start:
            decision = PolicyDecision(
                allowed=False,
                reason="Current time is before the authorized time window.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision
        if scope.time_window_end and now > scope.time_window_end:
            decision = PolicyDecision(
                allowed=False,
                reason="Authorized time window has expired.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision

        if activity in scope.forbidden_activities:
            decision = PolicyDecision(
                allowed=False,
                reason=f"Activity '{activity}' is explicitly forbidden in scope.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision

        if scope.allowed_activities and activity not in scope.allowed_activities:
            decision = PolicyDecision(
                allowed=False,
                reason=f"Activity '{activity}' is not in the allowed_activities list.",
                activity=activity,
                case_id=scope.case_id,
            )
            self._emit(decision)
            return decision

        if asset_identifier is not None:
            out_ids = {a.identifier for a in scope.out_of_scope_assets}
            if asset_identifier in out_ids:
                decision = PolicyDecision(
                    allowed=False,
                    reason=f"Asset '{asset_identifier}' is explicitly out of scope.",
                    activity=activity,
                    case_id=scope.case_id,
                )
                self._emit(decision)
                return decision
            in_ids = {a.identifier for a in scope.in_scope_assets}
            if in_ids and asset_identifier not in in_ids:
                decision = PolicyDecision(
                    allowed=False,
                    reason=f"Asset '{asset_identifier}' is not in the in_scope list.",
                    activity=activity,
                    case_id=scope.case_id,
                )
                self._emit(decision)
                return decision

        if network_required:
            if scope.network_profile == NetworkProfile.OFFLINE:
                decision = PolicyDecision(
                    allowed=False,
                    reason="Network activity is required but network_profile is 'offline'.",
                    activity=activity,
                    case_id=scope.case_id,
                )
                self._emit(decision)
                return decision

        # High/critical risk actions still require granted + ready (already checked)
        decision = PolicyDecision(
            allowed=True,
            reason="Policy checks passed.",
            activity=activity,
            case_id=scope.case_id,
            details={"risk_level": risk_level, "network_required": network_required},
        )
        self._emit(decision, denied=False)
        return decision

    def _emit(self, decision: PolicyDecision, denied: bool = True) -> None:
        event_type = EventType.POLICY_DENIED if not decision.allowed else EventType.POLICY_CHECK
        if self._bus:
            self._bus.publish(
                SpectraEvent(
                    event_type=event_type,
                    case_id=decision.case_id,
                    message=decision.reason,
                    payload={
                        "activity": decision.activity,
                        "allowed": decision.allowed,
                        "details": decision.details or {},
                    },
                    actor="policy_engine",
                )
            )
        if not decision.allowed:
            logger.warning(
                "policy_denied",
                activity=decision.activity,
                reason=decision.reason,
                case_id=str(decision.case_id) if decision.case_id else None,
            )
        else:
            logger.info(
                "policy_allowed",
                activity=decision.activity,
                case_id=str(decision.case_id) if decision.case_id else None,
            )
