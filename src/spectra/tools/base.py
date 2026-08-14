"""Tool adapter abstraction and controlled execution.

No arbitrary shell execution. Adapters declare exact commands or use
safe, argument-validated helpers only.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from spectra.core.config import get_settings
from spectra.core.logging import get_logger
from spectra.events.bus import EventBus
from spectra.models.capability import Capability
from spectra.models.events import EventType, SpectraEvent
from spectra.models.scope import Scope
from spectra.policy.engine import PolicyDecision, PolicyEngine

logger = get_logger(__name__)

# Metacharacters that must never appear in argument tokens when shell=False is used
# (defense in depth — we still never use shell=True).
_UNSAFE_ARG = re.compile(r"[;&|`$<>\n\r]")


@dataclass
class ToolResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def resolve_allowed_binary(name: str) -> str | None:
    """Resolve binary only if it is on the configured allowlist and on PATH."""
    settings = get_settings()
    allowed = set(settings.allowed_binaries)
    if name not in allowed:
        return None
    return shutil.which(name)


def run_safe_command(
    cmd: list[str],
    *,
    timeout: int | None = None,
    cwd: str | Path | None = None,
) -> ToolResult:
    """Run a command with shell=False, allowlist, and metacharacter checks."""
    settings = get_settings()
    timeout = timeout or settings.max_command_timeout_seconds
    if not cmd:
        return ToolResult(success=False, error="Empty command")
    binary = cmd[0]
    # If path-like, use basename for allowlist check
    bin_name = Path(binary).name
    if bin_name not in settings.allowed_binaries:
        return ToolResult(success=False, error=f"Binary '{bin_name}' is not on the allowlist")
    resolved = shutil.which(binary) if "/" not in binary and not Path(binary).is_file() else binary
    if not resolved or (not Path(resolved).is_file() and shutil.which(bin_name) is None):
        # try which on basename
        resolved = shutil.which(bin_name)
        if not resolved:
            return ToolResult(success=False, error=f"Binary '{bin_name}' not found on PATH")
    for arg in cmd[1:]:
        if _UNSAFE_ARG.search(str(arg)):
            return ToolResult(success=False, error=f"Unsafe character in argument: {arg!r}")
    full = [resolved, *[str(a) for a in cmd[1:]]]
    try:
        proc = subprocess.run(
            full,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
        return ToolResult(
            success=proc.returncode == 0,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
            error=None if proc.returncode == 0 else (proc.stderr or f"exit {proc.returncode}"),
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"Command timed out after {timeout}s")
    except OSError as exc:
        return ToolResult(success=False, error=f"OS error: {exc}")


class ToolAdapter(ABC):
    name: str = "base"
    capability: Capability

    def __init__(self, policy: PolicyEngine, event_bus: EventBus | None = None) -> None:
        self.policy = policy
        self.event_bus = event_bus

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def execute(
        self,
        *,
        scope: Scope | None,
        case_id: UUID,
        inputs: dict[str, Any],
        timeout: int | None = None,
    ) -> ToolResult:
        ...

    def _check_policy(
        self,
        scope: Scope | None,
        activity: str,
        asset: str | None = None,
        network_required: bool = False,
        risk_level: str = "low",
        case_id: UUID | None = None,
    ) -> PolicyDecision:
        return self.policy.evaluate(
            scope,
            activity,
            asset_identifier=asset,
            network_required=network_required,
            risk_level=risk_level,
            case_id=case_id,
        )
