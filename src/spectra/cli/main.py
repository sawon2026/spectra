"""Spectra CLI — professional entry point."""

from __future__ import annotations

import sys
from typing import Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from spectra import __version__
from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities
from spectra.cases.service import CaseService
from spectra.core.config import get_settings
from spectra.core.db import init_db
from spectra.core.logging import setup_logging, get_logger
from spectra.models.case import CaseCreate
from spectra.models.scope import ScopeCreate, AuthStatus, NetworkProfile
from spectra.models.evidence import EvidenceCreate, EvidenceSourceType
from spectra.policy.engine import PolicyEngine

app = typer.Typer(
    name="spectra",
    help="Spectra — AI-Powered Security Research & Engineering Platform",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
logger = get_logger("cli")

case_app = typer.Typer(help="Case management")
scope_app = typer.Typer(help="Scope and authorization")
cap_app = typer.Typer(help="Capabilities")
app.add_typer(case_app, name="case")
app.add_typer(scope_app, name="scope")
app.add_typer(cap_app, name="capabilities")


def _svc() -> CaseService:
    return CaseService()


def _reg() -> CapabilityRegistry:
    return seed_builtin_capabilities()


@app.command()
def version() -> None:
    """Show Spectra version."""
    console.print(f"Spectra {__version__}")


@app.command()
def doctor() -> None:
    """Check core health and optional external tools."""
    setup_logging("INFO")
    settings = get_settings()
    console.print("[bold]Spectra Doctor[/bold]")
    console.print(f"Version: {__version__}")
    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"Data dir: {settings.data_dir}")

    try:
        init_db(settings)
        console.print("[green]✓[/green] Database initialization")
    except Exception as e:
        console.print(f"[red]✗[/red] Database: {e}")
        raise typer.Exit(1)

    try:
        reg = _reg()
        console.print(f"[green]✓[/green] Capability registry ({len(reg)} builtins)")
    except Exception as e:
        console.print(f"[red]✗[/red] Registry: {e}")
        raise typer.Exit(1)

    try:
        PolicyEngine()
        console.print("[green]✓[/green] Policy engine")
    except Exception as e:
        console.print(f"[red]✗[/red] Policy: {e}")
        raise typer.Exit(1)

    optional = ["jadx", "apktool", "yara", "file", "strings"]
    for bin_name in optional:
        import shutil
        found = shutil.which(bin_name)
        if found:
            console.print(f"[green]✓[/green] Optional tool: {bin_name} ({found})")
        else:
            console.print(f"[yellow]·[/yellow] Optional tool not found: {bin_name} (ok)")

    console.print("[bold green]Core health: OK[/bold green]")


@case_app.command("create")
def case_create(
    name: str = typer.Option(..., "--name", "-n", help="Case name"),
    description: str = typer.Option("", "--description", "-d"),
) -> None:
    """Create a new investigation case."""
    svc = _svc()
    case = svc.create_case(CaseCreate(name=name, description=description))
    console.print(f"[green]Created case[/green] {case.id}")
    console.print(f"  name: {case.name}")
    console.print(f"  status: {case.status.value}")


@case_app.command("list")
def case_list() -> None:
    """List cases."""
    svc = _svc()
    cases = svc.list_cases()
    if not cases:
        console.print("No cases.")
        return
    table = Table("ID", "Name", "Status", "Created")
    for c in cases:
        table.add_row(str(c.id)[:8] + "…", c.name, c.status.value, c.created_at.isoformat()[:19])
    console.print(table)


@case_app.command("get")
def case_get(case_id: str = typer.Argument(..., help="Case UUID")) -> None:
    """Get case details."""
    svc = _svc()
    case = svc.get_case(UUID(case_id))
    if not case:
        console.print("[red]Case not found[/red]")
        raise typer.Exit(1)
    console.print_json(data=case.model_dump(mode="json"))


@scope_app.command("set")
def scope_set(
    case_id: str = typer.Option(..., "--case", help="Case UUID"),
    auth: str = typer.Option("pending", "--auth", help="pending|granted|denied"),
    network: str = typer.Option("offline", "--network", help="offline|limited|full"),
    activity: Optional[list[str]] = typer.Option(None, "--activity", help="Allowed activity (repeatable)"),
) -> None:
    """Set or replace scope for a case."""
    svc = _svc()
    cid = UUID(case_id)
    if not svc.get_case(cid):
        console.print("[red]Case not found[/red]")
        raise typer.Exit(1)
    data = ScopeCreate(
        case_id=cid,
        auth_status=AuthStatus(auth),
        network_profile=NetworkProfile(network),
        allowed_activities=activity or [],
    )
    scope = svc.set_scope(data)
    console.print(f"[green]Scope set[/green] auth={scope.auth_status.value} network={scope.network_profile.value}")
    console.print(f"  ready_for_act={scope.ready_for_act}")


@scope_app.command("get")
def scope_get(case_id: str = typer.Option(..., "--case")) -> None:
    """Show scope for a case."""
    svc = _svc()
    scope = svc.get_scope(UUID(case_id))
    if not scope:
        console.print("No scope defined.")
        return
    console.print_json(data=scope.model_dump(mode="json"))


@cap_app.command("list")
def cap_list() -> None:
    """List registered capabilities."""
    reg = _reg()
    table = Table("Name", "Category", "Risk", "Network", "Mode")
    for c in reg.list():
        table.add_row(
            c.name,
            c.category.value,
            c.risk_level.value,
            "yes" if c.network_required else "no",
            c.execution_mode.value,
        )
    console.print(table)


@app.command()
def analyze(
    case_id: str = typer.Option(..., "--case"),
    tool: str = typer.Option(..., "--tool", help="Capability name"),
    path: Optional[str] = typer.Option(None, "--path"),
) -> None:
    """Run a capability against a path under policy control."""
    from spectra.tools.builtin import run_capability

    svc = _svc()
    cid = UUID(case_id)
    case = svc.get_case(cid)
    if not case:
        console.print("[red]Case not found[/red]")
        raise typer.Exit(1)
    scope = svc.get_scope(cid)
    reg = _reg()
    if tool not in reg:
        console.print(f"[red]Unknown capability: {tool}[/red]")
        raise typer.Exit(1)

    result = run_capability(
        tool,
        scope=scope,
        case_id=cid,
        path=path,
        policy=PolicyEngine(),
    )
    if not result.success:
        console.print(f"[red]Blocked or failed:[/red] {result.error}")
        raise typer.Exit(1)
    console.print("[green]Success[/green]")
    if result.stdout:
        console.print(result.stdout)
    if result.data:
        console.print_json(data=result.data)


@app.command()
def evidence_add(
    case_id: str = typer.Option(..., "--case"),
    title: str = typer.Option(..., "--title"),
    excerpt: str = typer.Option("", "--excerpt"),
) -> None:
    """Record evidence for a case."""
    svc = _svc()
    cid = UUID(case_id)
    if not svc.get_case(cid):
        console.print("[red]Case not found[/red]")
        raise typer.Exit(1)
    ev = svc.add_evidence(
        EvidenceCreate(
            case_id=cid,
            title=title,
            excerpt=excerpt,
            source_type=EvidenceSourceType.MANUAL,
        )
    )
    console.print(f"[green]Evidence recorded[/green] {ev.id} hash={ev.content_hash}")


if __name__ == "__main__":
    app()
