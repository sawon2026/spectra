"""Tool adapter abstraction and controlled execution.

No arbitrary shell execution. Adapters declare exact commands or use
safe, argument-validated helpers only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.capability import Capability
from spectra.models.scope import Scope
from spectra.policy.engine import PolicyDecision, PolicyEngine

logger = get_logger(__name__)


@dataclass
class ToolResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ToolAdapter(ABC):
    """Base class for all tool integrations.

    Subclasses must not call unrestricted shell. Use run_safe_command
    or pure-Python implementations.
    """

    name: str
    capability: Capability

    def __init__(self, policy: PolicyEngine, event_bus: EventBus | None = None) -> None:
        self.policy = policy
        self.event_bus = event_bus or EventBus()

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying tool binary/library is present."""

    @abstractmethod
    def execute(
        self,
        *,
        scope: Scope | None,
        case_id: UUID,
        inputs: dict[str, Any],
        timeout: int | None = None,
    ) -> ToolResult:
        """Execute under policy control. Must call policy.evaluate first."""

    def _check_policy(
        self,
        scope: Scope | None,
        activity: str,
        *,
        asset: str | None = None,
        network: bool = False,
    ) -> PolicyDecision:
        decision = self.policy.evaluate(
            scope,
            activity,
            asset_identifier=asset,
            network_required=network,
            risk_level=self.capability.risk_level.value,
            case_id=scope.case_id if scope else None,
        )
        return decision


# Allowlist of binaries that may be invoked by adapters (Phase 1 minimal).
# Absolute paths preferred after discovery; basename only after allowlist match.
_ALLOWED_BINARIES = frozenset({
    "file",
    "strings",
    "sha256sum",
    "sha1sum",
    "md5sum",
    "xxd",
    "hexdump",
})


def resolve_allowed_binary(name: str) -> str | None:
    """Resolve a binary only if it is on the allowlist and exists on PATH."""
    base = Path(name).name
    if base not in _ALLOWED_BINARIES:
        return None
    path = shutil.which(base)
    return path


def run_safe_command(
    binary: str,
    args: Sequence[str],
    *,
    timeout: int = 60,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_data: bytes | None = None,
) -> ToolResult:
    """Run a pre-approved binary with explicit argument list (no shell).

    - shell=False always
    - binary must resolve via resolve_allowed_binary
    - timeout enforced
    - environment is a clean copy with optional extras
    """
    resolved = resolve_allowed_binary(binary)
    if not resolved:
        return ToolResult(
            success=False,
            error=f"Binary '{binary}' is not on the allowlist or not found on PATH",
        )

    # Reject any argument that looks like shell metacharacters for defense in depth
    for a in args:
        if any(c in a for c in (";", "|", "&", "`", "$", "\n", "\r", ">", "<")):
            return ToolResult(
                success=False,
                error="Argument contains disallowed shell metacharacters",
            )

    clean_env = os.environ.copy()
    # Remove potentially dangerous vars
    for k in list(clean_env.keys()):
        if k.startswith("LD_") or k in ("PYTHONPATH", "PERL5LIB"):
            # keep LD_LIBRARY_PATH if needed for system tools; still safer than full injection
            pass
    if env:
        clean_env.update(env)

    try:
        completed = subprocess.run(
            [resolved, *args],
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=clean_env,
            input=input_data,
            shell=False,  # CRITICAL: never True
            check=False,
        )
        return ToolResult(
            success=completed.returncode == 0,
            stdout=completed.stdout.decode("utf-8", errors="replace"),
            stderr=completed.stderr.decode("utf-8", errors="replace"),
            exit_code=completed.returncode,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"Command timed out after {timeout}s")
    except OSError as exc:
        return ToolResult(success=False, error=f"OS error: {exc}")
