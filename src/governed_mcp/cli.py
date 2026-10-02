"""Command-line interface.

Commands:
    governed run       start the MCP server (streamable HTTP or stdio)
    governed verify    live demonstration of RLS + guardrails across roles
    governed eval      run the adversarial eval harness
    governed schema    print the published data surface
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from governed_mcp import __version__
from governed_mcp.config import DATASET_VERSION
from governed_mcp.core import describe_schema
from governed_mcp.models import CallerClaims, QueryResult

app = typer.Typer(
    help="Governor MCP — a read-only MCP server with row-level security and deterministic guardrails.",
    no_args_is_help=True,
)
console = Console()


def _render_result(title: str, r: QueryResult) -> None:
    if r.blocked:
        console.print(Panel(f"[red]BLOCKED[/] — {r.blocked_reason}", title=title))
        return
    status = "ok" if not any(f.severity.value == "blocking" for f in r.findings) else "warn"
    color = "green" if status == "ok" else "yellow"
    console.print(
        f"[{color}]{title}[/]: {r.visible_count} visible / {r.withheld_count} withheld "
        f"of {r.total_count} matched (v{DATASET_VERSION})"
    )


@app.command()
def run(
    transport: str = typer.Option("streamable-http", help="MCP transport: streamable-http or stdio"),
    host: str = typer.Option("0.0.0.0", help="Bind address (http transport)"),
    port: int = typer.Option(8000, help="Bind port (http transport)"),
) -> None:
    """Start the MCP server."""
    from governed_mcp.server import create_mcp

    mcp = create_mcp()
    mcp.run(transport=transport, host=host, port=port)


@app.command()
def verify() -> None:
    """Run a live demonstration of the RLS + guardrail boundaries."""
    from governed_mcp import core

    admin = CallerClaims(sub="admin-user", roles=["admin"])
    rm = CallerClaims(sub="rm-01", roles=["rm"], rm_id="rm-01")
    regional = CallerClaims(sub="north-director", roles=["regional_director"], region="north")
    nobody = CallerClaims(sub="anonymous", roles=[])

    console.print(Panel("Governor MCP — boundary demonstration", title="verify"))

    console.print("\n[bold]1. Admin — sees the whole book[/]")
    _render_result("customers (all)", core.query_customers(admin))
    _render_result("accounts (all)", core.query_accounts(admin))

    console.print("\n[bold]2. Relationship manager rm-01 — only their customers[/]")
    r = core.query_customers(rm)
    _render_result("customers (rm-01)", r)
    regions = {row["region"] for row in r.rows}
    console.print(f"   rm-01 regions visible: {sorted(regions)} (should be one region)")

    console.print("\n[bold]3. Regional director (north) — only the north region[/]")
    _render_result("customers (north)", core.query_customers(regional))

    console.print("\n[bold]4. Anonymous — fail-closed, sees nothing[/]")
    _render_result("customers (anonymous)", core.query_customers(nobody))

    console.print("\n[bold]5. Account masking[/]")
    a = core.query_accounts(admin, customer_id="cust-001")
    if a.rows:
        console.print(f"   sample account: {a.rows[0]}")
    else:
        console.print("   (no accounts for cust-001)")

    console.print("\n[bold]6. Aggregate (admin, by region)[/]")
    agg = core.aggregate_balances(admin, group_by="region")
    table = Table(box=box.SIMPLE)
    table.add_column("Region")
    table.add_column("Balance", justify="right")
    table.add_column("Accounts", justify="right")
    for row in agg.rows:
        table.add_row(str(row["group"]), f"${row['total_balance']:,.0f}", str(row["count"]))
    console.print(table)


@app.command()
def eval() -> None:
    """Run the adversarial eval harness."""
    from governed_mcp.evals.runner import run_all

    ok = run_all()
    raise typer.Exit(0 if ok else 1)


@app.command()
def schema() -> None:
    """Print the published data surface."""
    console.print_json(json.dumps(describe_schema(), indent=2))


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"governor-mcp {__version__}")


if __name__ == "__main__":
    app()
