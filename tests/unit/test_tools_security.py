"""Security tests for tool execution boundaries."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from spectra.models.scope import AuthStatus, NetworkProfile, Scope, ScopeAsset
from spectra.policy.engine import PolicyEngine
from spectra.tools.base import resolve_allowed_binary, run_safe_command
from spectra.tools.builtin import FileInfoAdapter, HashComputeAdapter


def test_disallowed_binary_rejected():
    assert resolve_allowed_binary("bash") is None
    assert resolve_allowed_binary("sh") is None
    assert resolve_allowed_binary("python") is None
    assert resolve_allowed_binary("curl") is None
    result = run_safe_command("bash", ["-c", "echo pwned"])
    assert result.success is False
    assert "allowlist" in (result.error or "").lower()


def test_shell_metacharacters_in_args_rejected():
    # even if binary were allowed, metacharacters must be blocked
    result = run_safe_command("file", ["-b", "foo; rm -rf /"])
    assert result.success is False
    err = (result.error or "").lower()
    assert "metacharacter" in err or "allowlist" in err


def test_file_info_requires_existing_file(policy: PolicyEngine, tmp_path: Path):
    adapter = FileInfoAdapter(policy)
    result = adapter.execute(
        scope=None,
        case_id=uuid4(),
        inputs={"path": str(tmp_path / "missing.bin")},
    )
    assert result.success is False


def test_hash_compute_works(policy: PolicyEngine, tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("hello spectra")
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.GRANTED,
        ready_for_act=True,
        network_profile=NetworkProfile.OFFLINE,
        allowed_activities=["hash-compute"],
    )
    adapter = HashComputeAdapter(policy)
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(f)})
    assert result.success is True
    assert len(result.stdout.strip()) == 64  # sha256 hex


def test_file_info_with_authorized_scope(policy: PolicyEngine, tmp_path: Path):
    f = tmp_path / "sample.bin"
    f.write_bytes(b"\x00\x01\x02")
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.GRANTED,
        ready_for_act=True,
        network_profile=NetworkProfile.OFFLINE,
        in_scope_assets=[ScopeAsset(identifier=str(f))],
        allowed_activities=["file-info"],
    )
    adapter = FileInfoAdapter(policy)
    # requires_authorization is False for file-info, so even without perfect asset match it may run
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(f)})
    # availability depends on host having `file`
    if adapter.is_available():
        assert result.success is True or result.error is None
    else:
        assert result.success is False


def test_hash_blocked_when_scope_pending(policy: PolicyEngine, tmp_path: Path, settings):
    """Regression: require_scope_for_execution must block even low-risk adapters."""
    # settings fixture already has require_scope_for_execution=True
    f = tmp_path / "sample.txt"
    f.write_text("hello")
    scope = Scope(
        case_id=uuid4(),
        auth_status=AuthStatus.PENDING,
        ready_for_act=False,
        network_profile=NetworkProfile.OFFLINE,
    )
    adapter = HashComputeAdapter(policy)
    result = adapter.execute(scope=scope, case_id=scope.case_id, inputs={"path": str(f)})
    assert result.success is False
    assert result.error is not None
    assert "granted" in result.error.lower() or "ready" in result.error.lower() or "scope" in result.error.lower()
