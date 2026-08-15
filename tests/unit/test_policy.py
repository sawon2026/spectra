"""Policy engine tests — critical security boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from spectra.models.scope import AuthStatus, NetworkProfile, Scope, ScopeAsset
from spectra.policy.engine import PolicyEngine


def _scope(**kwargs) -> Scope:
    defaults = dict(
        case_id=uuid4(),
        auth_status=AuthStatus.GRANTED,
        ready_for_act=True,
        network_profile=NetworkProfile.OFFLINE,
        in_scope_assets=[ScopeAsset(identifier="sample.bin")],
        allowed_activities=["file-info", "hash-compute", "strings-extract"],
    )
    defaults.update(kwargs)
    return Scope(**defaults)


def test_deny_without_scope(policy: PolicyEngine):
    d = policy.evaluate(None, "file-info")
    assert d.allowed is False
    assert "No scope" in d.reason


def test_deny_pending_auth(policy: PolicyEngine):
    s = _scope(auth_status=AuthStatus.PENDING)
    d = policy.evaluate(s, "file-info")
    assert d.allowed is False
    assert "granted" in d.reason


def test_deny_not_ready(policy: PolicyEngine):
    s = _scope(ready_for_act=False)
    d = policy.evaluate(s, "file-info")
    assert d.allowed is False
    assert "ready_for_act" in d.reason


def test_deny_forbidden_activity(policy: PolicyEngine):
    s = _scope(forbidden_activities=["exploit"])
    d = policy.evaluate(s, "exploit")
    assert d.allowed is False


def test_deny_activity_not_in_allowed(policy: PolicyEngine):
    s = _scope(allowed_activities=["file-info"])
    d = policy.evaluate(s, "network-scan")
    assert d.allowed is False


def test_deny_out_of_scope_asset(policy: PolicyEngine):
    s = _scope(
        in_scope_assets=[ScopeAsset(identifier="ok.bin")],
        out_of_scope_assets=[ScopeAsset(identifier="secret.bin")],
    )
    d = policy.evaluate(s, "file-info", asset_identifier="secret.bin")
    assert d.allowed is False


def test_deny_asset_not_in_list(policy: PolicyEngine):
    s = _scope(in_scope_assets=[ScopeAsset(identifier="ok.bin")])
    d = policy.evaluate(s, "file-info", asset_identifier="other.bin")
    assert d.allowed is False


def test_deny_network_when_offline(policy: PolicyEngine):
    s = _scope(
        network_profile=NetworkProfile.OFFLINE,
        allowed_activities=["fetch-url", "file-info"],
    )
    d = policy.evaluate(s, "fetch-url", network_required=True)
    assert d.allowed is False
    assert "offline" in d.reason


def test_allow_happy_path(policy: PolicyEngine):
    s = _scope()
    d = policy.evaluate(s, "file-info", asset_identifier="sample.bin")
    assert d.allowed is True


def test_deny_expired_window(policy: PolicyEngine):
    past = datetime.now(UTC) - timedelta(hours=2)
    s = _scope(time_window_end=past)
    d = policy.evaluate(s, "file-info")
    assert d.allowed is False
    assert "expired" in d.reason.lower() or "window" in d.reason.lower()
