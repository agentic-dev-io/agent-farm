"""Agent Farm CLI — Typer-based command interface."""

from __future__ import annotations

import json
import os
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agent-farm",
    help="DuckDB-powered MCP server with Spec Engine for LLM agents.",
    rich_markup_mode="markdown",
)

spec_app = typer.Typer(help="Manage specs (agents, skills, schemas, workflows, ...).")
app.add_typer(spec_app, name="spec")

app_cmd = typer.Typer(help="MCP Apps — list and render UI templates.")
app.add_typer(app_cmd, name="app")

console = Console(stderr=True)
out = Console()


def init_farm(db: str = ":memory:", quiet: bool = False) -> tuple:
    """Initialize DuckDB + Spec Engine. Returns (connection, spec_engine, loaded_extensions)."""
    import duckdb

    from .main import (
        create_agent_tables,
        create_runtime_tables,
        extract_mcp_servers,
        find_mcp_config,
        load_core_extensions,
        load_sql_macros,
        setup_mcp_tables,
    )

    log = console.print if not quiet else lambda *a, **kw: None

    con = duckdb.connect(database=db)
    log(f"[dim]DB: {db}[/dim]")

    loaded_extensions = load_core_extensions(con)

    from .spec_engine import get_spec_engine, register_spec_engine_tools

    spec_engine = get_spec_engine(con)
    register_spec_engine_tools(con)

    mcp_configs = find_mcp_config()
    mcp_servers = extract_mcp_servers(mcp_configs)
    if mcp_servers:
        setup_mcp_tables(con, mcp_servers)
    else:
        con.sql("""
            CREATE OR REPLACE TABLE mcp_servers (
                name VARCHAR, command VARCHAR, args VARCHAR[],
                env JSON, source_config VARCHAR
            )
        """)

    try:
        from .udfs import register_udfs

        register_udfs(con)
    except Exception:
        pass

    create_agent_tables(con)
    create_runtime_tables(con)
    load_sql_macros(con)

    try:
        from .orgs import generate_org_seed_sql

        for stmt in generate_org_seed_sql().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    con.sql(stmt)
                except Exception:
                    pass
    except Exception:
        pass

    con.sql(f"""
        CREATE OR REPLACE TABLE loaded_extensions AS
        SELECT unnest({loaded_extensions!r}::VARCHAR[]) as extension_name
    """)

    return con, spec_engine, loaded_extensions


def _db_option() -> str:
    return os.environ.get("DUCKDB_DATABASE", ":memory:")


# ---------------------------------------------------------------------------
# App callback — default behavior (no subcommand) launches REPL
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
    org: Annotated[Optional[str], typer.Option("--org", help="Default org context.")] = None,
    session: Annotated[Optional[str], typer.Option("--session", help="Session ID.")] = None,
):
    """DuckDB-powered MCP server with Spec Engine for LLM agents."""
    if ctx.invoked_subcommand is not None:
        return
    from .repl import start_repl

    start_repl(db=db or _db_option(), org=org, session=session)


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------


@app.command()
def mcp(
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
    http_port: Annotated[Optional[int], typer.Option(help="Start HTTP API on this port.")] = None,
    http_api_key: Annotated[Optional[str], typer.Option(help="API key for HTTP server.")] = None,
):
    """Start the MCP server (stdio)."""
    db = db or _db_option()
    con, _, _ = init_farm(db)

    if http_port:
        auth = f"X-API-Key {http_api_key}" if http_api_key else ""
        auth_escaped = auth.replace("'", "''")
        try:
            con.sql(f"SELECT httpserve_start('0.0.0.0', {http_port}, '{auth_escaped}')")
            console.print(f"[green]HTTP server on port {http_port}[/green]")
        except Exception as e:
            console.print(f"[red]HTTP server failed: {e}[/red]")

    console.print("[green]Starting MCP Server...[/green]")
    try:
        con.sql("SELECT mcp_server_start('stdio', 'localhost', 0, '{}')")
    except Exception as e:
        console.print(f"[red]MCP Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """Show specs, extensions, and orgs in one view."""
    db = db or _db_option()
    _, engine, _ = init_farm(db, quiet=True)

    # Specs table
    data = engine.get_stats()
    specs_table = Table(title="Specs")
    specs_table.add_column("Kind", style="cyan")
    specs_table.add_column("Total", justify="right")
    specs_table.add_column("Active", justify="right", style="green")
    specs_table.add_column("Draft", justify="right", style="yellow")
    specs_table.add_column("Deprecated", justify="right", style="dim")

    grand_total = 0
    for kind, counts in sorted(data.get("specs_by_kind", {}).items()):
        specs_table.add_row(
            kind,
            str(counts["total"]),
            str(counts["active"]),
            str(counts["draft"]),
            str(counts["deprecated"]),
        )
        grand_total += counts["total"]

    specs_table.add_section()
    specs_table.add_row("[bold]Total[/bold]", f"[bold]{grand_total}[/bold]", "", "", "")
    out.print(specs_table)

    # Extensions
    exts = engine.get_loaded_extensions()
    out.print(f"\n[bold]Extensions[/bold] ({len(exts)}): {', '.join(sorted(exts))}")

    # Orgs table
    from .orgs import ORG_CONFIGS

    orgs_table = Table(title="Orgs")
    orgs_table.add_column("Name", style="cyan")
    orgs_table.add_column("Model", style="bold")
    orgs_table.add_column("Security")
    orgs_table.add_column("Tools", justify="right")

    for cfg in ORG_CONFIGS.values():
        orgs_table.add_row(
            cfg["name"],
            cfg["model_primary"],
            cfg["security_profile"].value,
            str(len(cfg.get("tools", []))),
        )

    out.print(orgs_table)


@app.command()
def sql(
    file: Annotated[str, typer.Argument(help="SQL file to execute.")],
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """Execute a SQL file against the initialized database."""
    db = db or _db_option()
    con, _, _ = init_farm(db, quiet=True)

    from .main import split_sql_statements

    with open(file, encoding="utf-8") as f:
        content = f.read()

    executed = 0
    for stmt in split_sql_statements(content):
        try:
            result = con.sql(stmt)
            if result:
                out.print(result.fetchdf().to_string())
            executed += 1
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    console.print(f"[dim]Executed {executed} statements from {file}[/dim]")


# ---------------------------------------------------------------------------
# spec subcommands
# ---------------------------------------------------------------------------


@spec_app.callback()
def spec_callback():
    """Manage specs (agents, skills, schemas, workflows, ...)."""


@spec_app.command("list")
def spec_list(
    kind: Annotated[Optional[str], typer.Option(help="Filter by kind.")] = None,
    status: Annotated[Optional[str], typer.Option(help="Filter by status.")] = None,
    limit: Annotated[int, typer.Option(help="Max results.")] = 50,
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """List specs with optional filters."""
    db = db or _db_option()
    _, engine, _ = init_farm(db, quiet=True)
    specs = engine.spec_list(kind=kind, status=status, limit=limit)

    if not specs:
        out.print("[dim]No specs found.[/dim]")
        return

    table = Table(title=f"Specs ({len(specs)})")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Kind", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Summary", max_width=50)

    for s in specs:
        status_style = {"active": "green", "draft": "yellow", "deprecated": "dim"}.get(
            s["status"], ""
        )
        table.add_row(
            str(s["id"]),
            s["kind"],
            s["name"],
            s.get("version", ""),
            f"[{status_style}]{s['status']}[/{status_style}]",
            (s.get("summary") or "")[:50],
        )

    out.print(table)


@spec_app.command("get")
def spec_get(
    id: Annotated[Optional[int], typer.Option(help="Spec ID.")] = None,
    kind: Annotated[Optional[str], typer.Option(help="Spec kind.")] = None,
    name: Annotated[Optional[str], typer.Option(help="Spec name.")] = None,
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """Get a single spec by ID or kind+name."""
    db = db or _db_option()
    _, engine, _ = init_farm(db, quiet=True)

    if id is None and (kind is None or name is None):
        console.print("[red]Provide --id or both --kind and --name.[/red]")
        raise typer.Exit(1)

    spec = engine.spec_get(id=id, kind=kind, name=name)
    if not spec:
        console.print("[red]Spec not found.[/red]")
        raise typer.Exit(1)

    out.print_json(json.dumps(spec, indent=2, default=str))


@spec_app.command("search")
def spec_search(
    query: Annotated[str, typer.Argument(help="Search query.")],
    limit: Annotated[int, typer.Option(help="Max results.")] = 20,
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """Search specs by name, summary, or docs."""
    db = db or _db_option()
    _, engine, _ = init_farm(db, quiet=True)
    specs = engine.spec_search(query=query, limit=limit)

    if not specs:
        out.print("[dim]No results.[/dim]")
        return

    table = Table(title=f"Search: '{query}' ({len(specs)} results)")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Kind", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Summary", max_width=60)

    for s in specs:
        table.add_row(
            str(s["id"]),
            s["kind"],
            s["name"],
            s["status"],
            (s.get("summary") or "")[:60],
        )

    out.print(table)


# ---------------------------------------------------------------------------
# app subcommands
# ---------------------------------------------------------------------------


@app_cmd.callback()
def app_callback():
    """MCP Apps — list and render UI templates."""


@app_cmd.command("list")
def app_list(
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """List available MCP apps."""
    db = db or _db_option()
    con, _, _ = init_farm(db, quiet=True)

    result = con.sql("SELECT id, name, app_type, description, org_id FROM mcp_apps ORDER BY id")
    rows = result.fetchall()

    if not rows:
        out.print("[dim]No apps found.[/dim]")
        return

    table = Table(title=f"MCP Apps ({len(rows)})")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Description", max_width=50)
    table.add_column("Org", style="dim")

    for row in rows:
        table.add_row(str(row[0]), row[1], row[2], (row[3] or "")[:50], row[4] or "")

    out.print(table)


@app_cmd.command("render")
def app_render(
    app_id: Annotated[int, typer.Argument(help="App ID to render.")],
    instance_id: Annotated[str, typer.Option(help="Instance ID.")] = "cli",
    input_json: Annotated[str, typer.Option("--input", help="JSON input for the app.")] = "{}",
    db: Annotated[str, typer.Option("--db", help="DuckDB database path.")] = "",
):
    """Render an MCP app template."""
    db = db or _db_option()
    con, _, _ = init_farm(db, quiet=True)

    input_escaped = input_json.replace("'", "''")
    instance_escaped = instance_id.replace("'", "''")
    try:
        result = con.sql(f"SELECT render_app({app_id}, '{instance_escaped}', '{input_escaped}')")
        row = result.fetchone()
        if row:
            out.print(row[0])
    except Exception as e:
        console.print(f"[red]Render failed: {e}[/red]")
        raise typer.Exit(1)


def cli():
    """CLI entry point."""
    app()
