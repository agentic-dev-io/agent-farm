"""Interactive REPL for Agent Farm — chat with AI agents, run slash-commands."""

from __future__ import annotations

import json
import logging
import shlex
from datetime import datetime, timezone

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .orgs import ORG_CONFIGS, ORG_SYSTEM_PROMPTS
from .schemas import OrgType
from .udfs import chat_with_model, stream_model_response

log = logging.getLogger(__name__)
out = Console()

_ORG_LOOKUP: dict[str, OrgType] = {t.value: t for t in OrgType}


def _parse_args(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _resolve_org(name: str) -> OrgType | None:
    return _ORG_LOOKUP.get(name.lower())


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------


def _save_session(
    con,
    session_id: str,
    org: OrgType,
    messages: list[dict],
) -> None:
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO agent_sessions
                (id, agent_id, started_at, status, context, messages)
            VALUES (?, NULL, ?, 'active', ?, ?)
            """,
            [
                session_id,
                datetime.now(timezone.utc).isoformat(),
                json.dumps({"org": org.value}),
                json.dumps(messages),
            ],
        )
    except Exception as exc:
        log.debug("session save failed: %s", exc)


def _load_session(con, session_id: str) -> tuple[str | None, list[dict]]:
    try:
        row = con.execute(
            "SELECT context, messages FROM agent_sessions WHERE id = ?",
            [session_id],
        ).fetchone()
        if row:
            ctx = json.loads(row[0]) if row[0] else {}
            msgs = json.loads(row[1]) if row[1] else []
            return ctx.get("org"), msgs
    except Exception as exc:
        log.debug("session load failed: %s", exc)
    return None, []


# ---------------------------------------------------------------------------
# Slash-command handlers
# ---------------------------------------------------------------------------


def _cmd_help() -> None:
    help_text = (
        "[bold cyan]/help[/]            Show this help\n"
        "[bold cyan]/org list[/]        List organisations\n"
        "[bold cyan]/org <name>[/]      Switch organisation\n"
        "[bold cyan]/spec list[/]       List specs  [dim](--kind <k>)[/dim]\n"
        "[bold cyan]/spec search <q>[/] Search specs\n"
        "[bold cyan]/status[/]          Show summary\n"
        "[bold cyan]/sql <query>[/]     Execute raw SQL\n"
        "[bold cyan]/session[/]         Show current session info\n"
        "[bold cyan]/exit[/]            Quit  [dim](/quit, /q)[/dim]\n"
    )
    out.print(Panel(help_text, title="Commands", border_style="cyan"))


def _cmd_org_list(current: OrgType) -> None:
    table = Table(title="Organisations")
    table.add_column("", width=2)
    table.add_column("Name", style="bold")
    table.add_column("Model")
    table.add_column("Security")
    table.add_column("Tools", justify="right")

    for org_type, cfg in ORG_CONFIGS.items():
        marker = "[green]*[/green]" if org_type == current else ""
        table.add_row(
            marker,
            cfg["name"],
            cfg["model_primary"],
            cfg["security_profile"].value,
            str(len(cfg.get("tools", []))),
        )

    out.print(table)


def _cmd_org_switch(name: str, current: OrgType) -> OrgType:
    new = _resolve_org(name)
    if new is None:
        out.print(f"[red]Unknown org:[/red] {name}")
        return current
    cfg = ORG_CONFIGS[new]
    out.print(f"Switched to [bold]{cfg['name']}[/bold] ({cfg['model_primary']})")
    return new


def _cmd_spec_list(engine, args: list[str]) -> None:
    kind = None
    for i, a in enumerate(args):
        if a == "--kind" and i + 1 < len(args):
            kind = args[i + 1]
    specs = engine.spec_list(kind=kind, limit=20)
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
        st = s.get("status", "")
        style = {"active": "green", "draft": "yellow", "deprecated": "dim"}.get(st, "")
        table.add_row(
            str(s["id"]),
            s["kind"],
            s["name"],
            s.get("version", ""),
            f"[{style}]{st}[/{style}]" if style else st,
            (s.get("summary") or "")[:50],
        )
    out.print(table)


def _cmd_spec_search(engine, query: str) -> None:
    specs = engine.spec_search(query=query, limit=10)
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
            s.get("status", ""),
            (s.get("summary") or "")[:60],
        )
    out.print(table)


def _cmd_status(engine) -> None:
    stats = engine.get_stats()
    spec_total = sum(v["total"] for v in stats.get("specs_by_kind", {}).values())
    ext_count = len(engine.get_loaded_extensions())
    org_count = len(ORG_CONFIGS)
    out.print(
        f"[bold]{spec_total}[/bold] specs, "
        f"[bold]{ext_count}[/bold] extensions, "
        f"[bold]{org_count}[/bold] orgs"
    )


def _cmd_sql(con, query: str) -> None:
    try:
        result = con.sql(query)
        if result:
            out.print(result.fetchdf().to_string())
    except Exception as exc:
        out.print(f"[red]SQL error:[/red] {exc}")


def _cmd_session(session_id: str | None, org: OrgType, messages: list[dict]) -> None:
    sid = session_id or "(ephemeral)"
    org_name = ORG_CONFIGS[org]["name"]
    out.print(
        f"session=[bold]{sid}[/bold]  "
        f"org=[bold]{org_name}[/bold]  "
        f"messages=[bold]{len(messages)}[/bold]"
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def _chat(org: OrgType, user_input: str, messages: list[dict]) -> str | None:
    cfg = ORG_CONFIGS[org]
    model = cfg["model_primary"]
    system_prompt = ORG_SYSTEM_PROMPTS[org]

    messages.append({"role": "user", "content": user_input})
    content_chunks: list[str] = []
    try:
        for chunk in stream_model_response(model, messages, system_prompt=system_prompt):
            out.print(chunk, end="")
            content_chunks.append(chunk)
        if content_chunks:
            out.print()
            content = "".join(content_chunks)
        else:
            data = chat_with_model(model, messages, system_prompt=system_prompt)
            if "error" in data:
                out.print(f"[red]Error:[/red] {data['error']}")
                messages.pop()
                return None
            content = data.get("content", "")
            out.print(Markdown(content))
    except Exception as exc:
        data = chat_with_model(model, messages, system_prompt=system_prompt)
        if "error" in data:
            out.print(f"[red]Error:[/red] {data['error']}")
            messages.pop()
            return None
        log.debug("streaming fallback: %s", exc)
        content = data.get("content", "")
        out.print(Markdown(content))

    messages.append({"role": "assistant", "content": content})
    return content


# ---------------------------------------------------------------------------
# REPL entry point
# ---------------------------------------------------------------------------


def start_repl(
    db: str = ":memory:",
    org: str | None = None,
    session: str | None = None,
) -> None:
    from .cli import init_farm

    con, engine, _ = init_farm(db)

    org_type = _resolve_org(org) if org else OrgType.ORCHESTRATOR
    if org_type is None:
        out.print(f"[red]Unknown org '{org}', falling back to orchestrator.[/red]")
        org_type = OrgType.ORCHESTRATOR

    session_id = session
    messages: list[dict] = []

    if session_id:
        saved_org, saved_msgs = _load_session(con, session_id)
        if saved_msgs:
            messages = saved_msgs
            if saved_org:
                resolved = _resolve_org(saved_org)
                if resolved:
                    org_type = resolved

    cfg = ORG_CONFIGS[org_type]
    out.print(
        Panel(
            f"[bold]{cfg['name']}[/bold] — {cfg['model_primary']}\n"
            "[dim]Type /help for commands, /exit to quit.[/dim]",
            title="Agent Farm REPL",
            border_style="green",
        )
    )

    while True:
        prompt_text = f"[{cfg['name']}]> "
        try:
            user_input = out.input(prompt_text)
        except (KeyboardInterrupt, EOFError):
            out.print("Bye.")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = _parse_args(user_input)
            cmd = parts[0].lower()
            rest = parts[1:]

            if cmd == "/help":
                _cmd_help()

            elif cmd == "/org":
                if not rest or rest[0] == "list":
                    _cmd_org_list(org_type)
                else:
                    org_type = _cmd_org_switch(rest[0], org_type)
                    cfg = ORG_CONFIGS[org_type]

            elif cmd == "/spec":
                if not rest or rest[0] == "list":
                    _cmd_spec_list(engine, rest[1:] if rest else [])
                elif rest[0] == "search" and len(rest) > 1:
                    _cmd_spec_search(engine, " ".join(rest[1:]))
                else:
                    out.print("[dim]Usage: /spec list [--kind <k>] | /spec search <query>[/dim]")

            elif cmd == "/status":
                _cmd_status(engine)

            elif cmd == "/sql" and rest:
                _cmd_sql(con, " ".join(rest))

            elif cmd == "/session":
                _cmd_session(session_id, org_type, messages)

            elif cmd in ("/exit", "/quit", "/q"):
                if session_id:
                    _save_session(con, session_id, org_type, messages)
                out.print("Bye.")
                break

            else:
                out.print(f"[dim]Unknown command: {cmd}  (try /help)[/dim]")

        else:
            _chat(org_type, user_input, messages)
            if session_id:
                _save_session(con, session_id, org_type, messages)
