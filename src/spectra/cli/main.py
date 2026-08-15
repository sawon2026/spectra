"""Spectra CLI entry point."""

from __future__ import annotations

from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from spectra import __version__
from spectra.capabilities.registry import CapabilityRegistry, seed_builtin_capabilities
from spectra.cases.service import CaseService
from spectra.core.config import get_settings
from spectra.core.db import init_db
from spectra.core.logging import get_logger, setup_logging
from spectra.events.bus import EventBus
from spectra.evidence.service import EvidenceService
from spectra.models.case import CaseCreate, CaseStatus
from spectra.models.evidence import EvidenceCreate, EvidenceSourceType
from spectra.models.scope import AuthStatus, NetworkProfile, ScopeAsset, ScopeCreate
from spectra.policy.engine import PolicyEngine
from spectra.tools.builtin import FileInfoAdapter, HashComputeAdapter

app = typer.Typer(
    name="spectra",
    help="Spectra — AI-Powered Security Research & Engineering Platform",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
logger = get_logger("cli")

# Shared services (initialized on first use)
_bus: EventBus | None = None
_policy: PolicyEngine | None = None
_cases: CaseService | None = None
_caps: CapabilityRegistry | None = None


def _init() -> None:
    global _bus, _policy, _cases, _caps
    if _bus is not None:
        return
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db(settings)
    _bus = EventBus(persist=True)
    _policy = PolicyEngine(event_bus=_bus)
    _cases = CaseService(event_bus=_bus)
    _caps = CapabilityRegistry(event_bus=_bus)
    seed_builtin_capabilities(_caps)


@app.command()
def version() -> None:
    """Show Spectra version."""
    console.print(f"Spectra {__version__}")


@app.command("doctor")
def doctor() -> None:
    """Health check: core, database, policy, capabilities, external tools, AI."""
    import shutil

    _init()
    settings = get_settings()
    console.print(f"[bold]Spectra {__version__}[/bold]")
    console.print("")
    console.print("[bold]Core[/bold]: OK")
    console.print(f"  Data dir: {settings.data_dir}")
    console.print(f"  Require scope: {settings.require_scope_for_execution}")
    console.print("[bold]Database[/bold]: OK")
    console.print(f"  {settings.get_database_url()}")
    console.print("[bold]Policy[/bold]: OK")
    console.print("  PolicyEngine loaded (strict authorization gate)")
    assert _caps is not None
    caps = _caps.list()
    console.print(f"[bold]Capabilities[/bold]: {len(caps)} registered")

    table = Table(title="Adapters")
    table.add_column("Name")
    table.add_column("Status")
    from spectra.tools.android.apk_meta import ApkMetadataAdapter
    from spectra.tools.builtin import StringsExtractAdapter
    for adapter_cls in (FileInfoAdapter, HashComputeAdapter, StringsExtractAdapter, ApkMetadataAdapter):
        ad = adapter_cls(policy=_policy, event_bus=_bus)  # type: ignore[arg-type]
        table.add_row(ad.name, "OK" if ad.is_available() else "UNAVAILABLE")
    console.print(table)

    ext = Table(title="External Tools (optional)")
    ext.add_column("Tool")
    ext.add_column("Status")
    for name in ("jadx", "apktool", "yara", "aapt"):
        path = shutil.which(name)
        ext.add_row(name.upper() if name != "aapt" else name, "OK" if path else "NOT INSTALLED")
    console.print(ext)

    console.print("[bold]AI Providers[/bold]: NOT CONFIGURED (deterministic classifier active)")
    console.print("")
    console.print("[green]Doctor complete — optional tools missing is not a core failure.[/green]")


@app.command("case")
def case_cmd(
    action: str = typer.Argument(..., help="create | list | show | status"),
    name: str | None = typer.Option(None, "--name", "-n"),
    description: str = typer.Option("", "--description", "-d"),
    case_id: str | None = typer.Option(None, "--id"),
    status: str | None = typer.Option(None, "--status"),
) -> None:
    """Manage cases."""
    _init()
    assert _cases is not None

    if action == "create":
        if not name:
            console.print("[red]--name is required for create[/red]")
            raise typer.Exit(1)
        try:
            case = _cases.create(CaseCreate(name=name, description=description))
            console.print(f"[green]Created case[/green] {case.id}  name={case.name}")
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    elif action == "list":
        cases = _cases.list_cases()
        table = Table(title="Cases")
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Created")
        for c in cases:
            table.add_row(str(c.id), c.name, c.status.value, c.created_at.isoformat())
        console.print(table)

    elif action == "show":
        c = None
        if case_id:
            c = _cases.get(UUID(case_id))
        elif name:
            c = _cases.get_by_name(name)
        else:
            console.print("[red]Provide --id or --name[/red]")
            raise typer.Exit(1)
        if c is None:
            console.print("[red]Case not found[/red]")
            raise typer.Exit(1)
        console.print(c.model_dump_json(indent=2))

    elif action == "status":
        if not case_id or not status:
            console.print("[red]--id and --status required[/red]")
            raise typer.Exit(1)
        try:
            st = CaseStatus(status)
        except ValueError:
            console.print(f"[red]Invalid status. Choose from: {[s.value for s in CaseStatus]}[/red]")
            raise typer.Exit(1)
        c = _cases.update_status(UUID(case_id), st)
        console.print(f"Updated status to {c.status.value}")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command("scope")
def scope_cmd(
    action: str = typer.Argument(..., help="set | show"),
    case_id: str = typer.Option(..., "--case", "-c", help="Case UUID"),
    auth: str = typer.Option("pending", "--auth", help="pending|granted|denied|expired"),
    network: str = typer.Option("offline", "--network", help="offline|lab_only|authorized_target_only|unrestricted_lab"),
    asset: list[str] | None = typer.Option(None, "--asset", help="In-scope asset identifier (repeatable)"),
    activity: list[str] | None = typer.Option(None, "--activity", help="Allowed activity (repeatable)"),
) -> None:
    """Manage investigation scope and authorization."""
    _init()
    assert _cases is not None
    cid = UUID(case_id)

    if action == "set":
        try:
            auth_status = AuthStatus(auth)
            net = NetworkProfile(network)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        assets = [ScopeAsset(identifier=a) for a in (asset or [])]
        activities = activity or []
        scope = _cases.set_scope(
            ScopeCreate(
                case_id=cid,
                auth_status=auth_status,
                auth_basis="cli",
                in_scope_assets=assets,
                allowed_activities=activities,
                network_profile=net,
            )
        )
        console.print(
            f"[green]Scope set[/green] auth={scope.auth_status.value} "
            f"ready_for_act={scope.ready_for_act} network={scope.network_profile.value}"
        )

    elif action == "show":
        shown = _cases.get_scope(cid)
        if shown is None:
            console.print("[yellow]No scope defined for this case[/yellow]")
            raise typer.Exit(0)
        console.print(shown.model_dump_json(indent=2))

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


@app.command("capabilities")
def capabilities_cmd(
    action: str = typer.Argument("list", help="list"),
) -> None:
    """List registered capabilities."""
    _init()
    assert _caps is not None
    caps = _caps.list()
    table = Table(title="Capabilities")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Risk")
    table.add_column("Auth required")
    table.add_column("Health")
    for c in caps:
        table.add_row(
            c.name,
            c.category.value,
            c.risk_level.value,
            "yes" if c.requires_authorization else "no",
            c.health_status,
        )
    console.print(table)


@app.command("analyze")
def analyze_cmd(
    case_id: str = typer.Option(..., "--case", "-c"),
    tool: str = typer.Option(..., "--tool", "-t", help="file-info | hash-compute"),
    path: str = typer.Option(..., "--path", "-p"),
) -> None:
    """Run a built-in analysis tool under policy control."""
    _init()
    assert _cases is not None and _policy is not None and _bus is not None
    cid = UUID(case_id)
    scope = _cases.get_scope(cid)

    adapters = {
        "file-info": FileInfoAdapter(_policy, _bus),
        "hash-compute": HashComputeAdapter(_policy, _bus),
    }
    adapter = adapters.get(tool)
    if not adapter:
        console.print(f"[red]Unknown tool. Available: {list(adapters)}[/red]")
        raise typer.Exit(1)

    result = adapter.execute(scope=scope, case_id=cid, inputs={"path": path})
    if result.success:
        console.print("[green]Success[/green]")
        if result.stdout:
            console.print(result.stdout.strip())
        if result.metadata:
            console.print(result.metadata)
    else:
        console.print(f"[red]Failed:[/red] {result.error or result.stderr}")
        raise typer.Exit(1)


@app.command("evidence")
def evidence_cmd(
    action: str = typer.Argument(..., help="list | add"),
    case_id: str = typer.Option(..., "--case", "-c"),
    title: str | None = typer.Option(None, "--title"),
    excerpt: str = typer.Option("", "--excerpt"),
) -> None:
    """List or record evidence for a case."""
    _init()
    assert _bus is not None
    svc = EvidenceService(event_bus=_bus)
    cid = UUID(case_id)

    if action == "list":
        items = svc.list_for_case(cid)
        table = Table(title="Evidence")
        table.add_column("ID")
        table.add_column("Title")
        table.add_column("Source")
        table.add_column("Hash")
        for e in items:
            table.add_row(
                str(e.id),
                e.title,
                e.source_type.value,
                (e.content_hash or "")[:16],
            )
        console.print(table)

    elif action == "add":
        if not title:
            console.print("[red]--title required[/red]")
            raise typer.Exit(1)
        ev = svc.record(
            EvidenceCreate(
                case_id=cid,
                title=title,
                source_type=EvidenceSourceType.MANUAL,
                raw_excerpt=excerpt,
            )
        )
        console.print(f"[green]Recorded evidence[/green] {ev.id}")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
