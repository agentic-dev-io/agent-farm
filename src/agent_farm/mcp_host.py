"""MCP stdio host for Agent Farm.

Identity:
  This server IS AgentFarmer - the Orchestrator.

Architecture:
  Transport:    FastMCP (mcp Python SDK) — stdio, blocks until disconnect.
  Bootstrap:    DuckDB bootstrap runs in a background thread so the MCP
                initialize handshake completes immediately (no timeout).
  Instructions: Live orchestrator system prompt from orgs.py.
  Prompts:      One per org role.
  Resources:    Org prompts, tools schema, dispatch guide, app UI instances.
  Tools:        4 org dispatch tools + query fallback.
                UI tools call open_app() DuckDB macro, render via minijinja
                extension, store HTML in mcp_app_instances, return
                _meta.ui.resourceUri pointing to the instance resource.

UI rendering pipeline (Python runtime slot):
  DuckDB macros open_app/render_app return {"status": "pending_render", ...}
  -> _open_and_render() resolves template (mcp_app_templates table or
     skill template files) -> minijinja_render() DuckDB extension ->
     stored in mcp_app_instances.rendered_html ->
     agent-farm://ui/{instance_id} resource serves the HTML.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import duckdb
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from .orgs import ORG_SYSTEM_PROMPTS
from .schemas import OrgType

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state — set by background bootstrap thread
# ---------------------------------------------------------------------------
_con: duckdb.DuckDBPyConnection | None = None
_ready = threading.Event()
_bootstrap_error: str | None = None  # captured if bootstrap fails

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMPLATE_DIR = _PROJECT_ROOT / ".claude" / "Skills" / "duck-agent-system"

# Pre-bootstrap query queue: avoids MCP tool-call timeouts during startup.
_pending_queries_lock = threading.Lock()
_pending_queries: dict[str, str] = {}
_preboot_ui: dict[str, str] = {}

_ORG_MAP: dict[str, OrgType] = {
    "dev": OrgType.DEV,
    "ops": OrgType.OPS,
    "research": OrgType.RESEARCH,
    "studio": OrgType.STUDIO,
    "orchestrator": OrgType.ORCHESTRATOR,
}

# app_id -> template filename in _TEMPLATE_DIR (fallback if mcp_app_templates empty)
_APP_TEMPLATE_FILES: dict[str, str] = {
    "app.dashboard": "dashboard.html",
    "app.task-detail": "task-detail.html",
}


# ---------------------------------------------------------------------------
# Bootstrap thread
# ---------------------------------------------------------------------------

def _bootstrap_thread(db_path: str, http_port: int | None, http_api_key: str | None) -> None:
    global _con, _bootstrap_error
    try:
        from .logging_config import setup_logging
        from .main import (
            AGENT_FARM_DIR,
            bootstrap_db,
            cleanup_stale_files,
            ensure_single_mcp_instance,
        )
        setup_logging(log_file=str(AGENT_FARM_DIR / "agent_farm.log"), stdio_safe=True)
        ensure_single_mcp_instance()
        cleanup_stale_files()
        con = bootstrap_db(db_path)
        _con = con
        if http_port:
            from .duckdb_utils import start_http_server
            start_http_server(con, http_port, http_api_key)
        log.info("Bootstrap complete — MCP tools ready")
    except Exception as exc:
        import traceback
        _bootstrap_error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        log.error("Bootstrap failed: %s", _bootstrap_error)
    finally:
        _ready.set()

    # After bootstrap, execute any queued startup queries.
    try:
        _drain_pending_queries()
    except Exception as exc:  # pragma: no cover
        log.error("Pending query drain failed: %s", exc)


def _wait(timeout: float = 120.0) -> bool:
    return _ready.wait(timeout=timeout)


def _check_ready(timeout: float = 120.0) -> str | None:
    """Wait for bootstrap; return error string if failed or timed out, else None."""
    if not _ready.wait(timeout=timeout):
        return "Bootstrap timed out — DuckDB not ready after 120s"
    if _con is None:
        return f"Bootstrap failed: {_bootstrap_error or 'unknown error'}"
    return None


def _check_ready_now() -> str | None:
    """Non-blocking readiness check.

    MCP clients often issue List*Requests immediately after connect; blocking here
    can cause client-side timeouts even though bootstrap would finish shortly.
    """
    if not _ready.is_set():
        return "Bootstrap not ready yet"
    if _con is None:
        return f"Bootstrap failed: {_bootstrap_error or 'unknown error'}"
    return None


def _queue_query(sql: str) -> str:
    """Queue a SQL query to run after bootstrap; return instance_id for UI."""
    import uuid as _uuid

    iid = "pre-" + _uuid.uuid4().hex[:10]
    html = (
        "<div style=\"font-family: ui-sans-serif, system-ui; padding: 12px\">"
        "<h3 style=\"margin:0 0 8px 0\">Server initializing…</h3>"
        "<p style=\"margin:0 0 8px 0\">This query will run automatically once bootstrap finishes.</p>"
        f"<pre style=\"white-space: pre-wrap; margin:0; padding:10px; background:#111; color:#eee; border-radius:8px\">{sql}</pre>"
        "</div>"
    )
    with _pending_queries_lock:
        _pending_queries[iid] = sql
        _preboot_ui[iid] = html
    return iid


def _drain_pending_queries() -> None:
    """Execute queued queries once bootstrap is ready."""
    if _con is None:
        return
    with _pending_queries_lock:
        items = list(_pending_queries.items())
        _pending_queries.clear()
    for iid, sql in items:
        try:
            result = _con.execute(sql)
            if result is None or not result.description:
                html = "<pre>(statement executed, no rows returned)</pre>"
            else:
                rows = result.fetchall()
                cols = [d[0] for d in result.description]
                if len(rows) == 1 and len(cols) == 1:
                    val = rows[0][0]
                    handled = _handle_pending_action(val)
                    if handled is not val:
                        html = f"<pre>{handled}</pre>"
                    elif isinstance(val, str) and val.strip().startswith("<"):
                        html = val
                    else:
                        html = f"<pre>{_fmt_rows(rows, cols)}</pre>"
                else:
                    html = f"<pre>{_fmt_rows(rows, cols)}</pre>"
        except Exception as exc:
            html = f"<pre>Error: {exc}</pre>"

        # Persist final HTML in the standard app-instance store.
        _store_instance(iid, "query", "query", {"sql": sql}, html)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_rows(rows: list, columns: list[str]) -> str:
    if not rows:
        return "(0 rows)"
    col_str = " | ".join(columns)
    lines = [col_str, "-" * max(len(col_str), 10)]
    for row in rows[:500]:
        lines.append(" | ".join("NULL" if v is None else str(v) for v in row))
    if len(rows) > 500:
        lines.append(f"... ({len(rows)} total, showing 500)")
    return "\n".join(lines)


def _dispatch(tool_name: str, task: str, session_id: str) -> str:
    if not session_id:
        row = _con.execute("SELECT gen_random_uuid()::VARCHAR").fetchone()
        session_id = row[0] if row else "unknown"
    params = json.dumps({"task": task})
    result = _con.execute(
        "SELECT execute_orchestrator_tool(?, ?, ?::JSON)",
        [session_id, tool_name, params],
    ).fetchone()
    raw = result[0] if result else None
    # Intercept pending DML actions (e.g. notes_board_create/update)
    handled = _handle_pending_action(raw)
    return str(handled) if handled is not None else "(no result)"


def _tool_result(text: str, resource_uri: str | None = None) -> CallToolResult:
    meta: dict[str, Any] | None = {"ui": {"resourceUri": resource_uri}} if resource_uri else None
    return CallToolResult(content=[TextContent(type="text", text=text)], meta=meta)


# ---------------------------------------------------------------------------
# Pending-action runtime handler
# ---------------------------------------------------------------------------

def _handle_pending_action(result: Any) -> Any:
    """Handle DML sentinel values returned by DuckDB macros that cannot do DML directly.

    DuckDB macros are expressions — they cannot execute INSERT/UPDATE statements.
    Instead, macros that need to write data return a JSON sentinel:
        {"action": "<action_name>", "status": "pending_insert"|"pending_update", ...}

    This function intercepts those sentinels and performs the actual DML against
    lake.notes_board (shared persistent state across all sessions).

    Supported actions:
        notes_board_create  — INSERT into lake.notes_board
        notes_board_update  — UPDATE lake.notes_board SET content WHERE id

    Returns the result unchanged if it is not a recognised pending action.
    If DuckLake is unavailable, logs an error and returns an error JSON.
    """
    if _con is None:
        return result

    if isinstance(result, str):
        try:
            data: Any = json.loads(result)
        except Exception:
            return result  # not JSON
    elif isinstance(result, dict):
        data = result
    else:
        return result

    if not isinstance(data, dict):
        return result

    action = data.get("action")
    status = data.get("status")

    # ── notes_board_create ──────────────────────────────────────────────────
    if action == "notes_board_create" and status == "pending_insert":
        note_id = data.get("id") or f"note-{int(time.time())}"
        project = data.get("project") or ""
        title = data.get("title") or ""
        content = data.get("content") or ""
        try:
            _con.execute(
                """
                INSERT INTO lake.notes_board
                    (id, project, title, content, note_type, status, created_by,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, 'general', 'open', 'agent-farm', now(), now())
                """,
                [note_id, project, title, content],
            )
            out = {**data, "status": "ok", "persisted": "lake.notes_board"}
            log.info("Created note %s in lake.notes_board (project=%s)", note_id, project)
        except Exception as exc:
            log.error("Failed to persist note %s to lake.notes_board: %s", note_id, exc)
            out = {**data, "status": "error", "error": str(exc)}
        return json.dumps(out)

    # ── notes_board_update ──────────────────────────────────────────────────
    if action == "notes_board_update" and status == "pending_update":
        note_id = data.get("id") or ""
        content = data.get("content") or ""
        try:
            _con.execute(
                "UPDATE lake.notes_board SET content = ?, updated_at = now() WHERE id = ?",
                [content, note_id],
            )
            out = {**data, "status": "ok", "persisted": "lake.notes_board"}
            log.info("Updated note %s in lake.notes_board", note_id)
        except Exception as exc:
            log.error("Failed to update note %s in lake.notes_board: %s", note_id, exc)
            out = {**data, "status": "error", "error": str(exc)}
        return json.dumps(out)

    return result


# ---------------------------------------------------------------------------
# UI rendering — Python runtime slot for pending_render dispatches
# ---------------------------------------------------------------------------

def _resolve_template_info(app_id: str) -> tuple[str | None, str | None, str | None]:
    """Resolve template info for app_id.
    Returns (child_template, base_template_id, script_template_id).
    - child_template:    raw minijinja fragment (body content)
    - base_template_id:  id of the wrapping base template (e.g. 'base'), or None
    - script_template_id: id of matching script template (e.g. 'design-choices-script'), or None
    """
    try:
        row = _con.execute(
            "SELECT t.template, t.base_template, t.id "
            "FROM mcp_apps a "
            "JOIN mcp_app_templates t ON a.template_id = t.id "
            "WHERE a.id = ?", [app_id]
        ).fetchone()
        if row:
            child_tmpl, base_tmpl_id, tmpl_id = row
            # Convention: script template is stored as '{template_id}-script'
            script_id = f"{tmpl_id}-script" if tmpl_id else None
            return (child_tmpl or "", base_tmpl_id, script_id)
    except Exception:
        pass
    # Fallback: skill template files (no base composition)
    fname = _APP_TEMPLATE_FILES.get(app_id)
    if fname:
        p = _TEMPLATE_DIR / fname
        if p.exists():
            return (p.read_text(encoding="utf-8"), None, None)
    return (None, None, None)


def _get_template_content(template_id: str) -> str | None:
    """Fetch raw template text from mcp_app_templates by id."""
    try:
        row = _con.execute(
            "SELECT template FROM mcp_app_templates WHERE id = ?", [template_id]
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _compose_and_render(app_id: str, data: dict, instance_id: str = "") -> str:
    """Render app HTML with full base-template composition.

    Pipeline:
      1. Resolve child fragment + base_template_id + script_template_id
      2. Render child fragment with data              → content
      3. Render script template with data             → script  (if exists)
      4. Render base template with data+content+script → full HTML page

    Falls back to bare child HTML if no base template is defined.
    """
    child_template, base_template_id, script_template_id = _resolve_template_info(app_id)
    if not child_template:
        return f"<p>No template registered for app: {app_id}</p>"

    render_data = dict(data)
    render_data.setdefault("instance_id", instance_id)

    # Step 1: render child fragment
    child_html = _minijinja_render(child_template, render_data)

    # Step 2: no base template → fragment is already a full page
    if not base_template_id:
        return child_html

    # Step 3: render script (convention: {template_id}-script)
    script_content = ""
    if script_template_id:
        script_tmpl = _get_template_content(script_template_id)
        if script_tmpl:
            script_content = _minijinja_render(script_tmpl, render_data)

    # Step 4: compose fragment + script into base template
    base_template = _get_template_content(base_template_id)
    if not base_template:
        return child_html  # base template missing, return fragment as fallback

    base_data = dict(render_data)
    base_data["content"] = child_html
    base_data["script"] = script_content

    return _minijinja_render(base_template, base_data)


def _minijinja_render(template: str, data: dict) -> str:
    try:
        row = _con.execute(
            "SELECT minijinja_render(?, ?::JSON)",
            [template, json.dumps(data, default=str)],
        ).fetchone()
        return row[0] if row else "<p>Render returned nothing</p>"
    except Exception as exc:
        log.error("minijinja_render failed: %s", exc)
        return f"<p>Render error: {exc}</p>"


def _store_instance(instance_id: str, app_id: str, session_id: str,
                    input_data: dict, html: str) -> None:
    """Store rendered app instance in local DB and (if available) DuckLake for cross-session access."""
    input_json = json.dumps(input_data)
    # 1. Local session DB (fast; used by this process)
    try:
        _con.execute("""
            INSERT INTO mcp_app_instances
                (instance_id, app_id, session_id, status, input_data, rendered_html, created_at)
            VALUES (?, ?, ?, 'active', ?::JSON, ?, now())
            ON CONFLICT (instance_id) DO UPDATE SET
                rendered_html = excluded.rendered_html,
                status = 'active'
        """, [instance_id, app_id, session_id, input_json, html])
    except Exception as exc:
        log.warning("Could not store app instance locally %s: %s", instance_id, exc)

    # 2. DuckLake (persistent; visible to all MCP sessions)
    # DuckLake is required infrastructure — warn loudly if the write fails.
    try:
        _con.execute("""
            INSERT INTO lake.mcp_app_instances
                (instance_id, app_id, session_id, status, input_data, rendered_html, created_at)
            VALUES (?, ?, ?, 'active', ?::JSON, ?, now())
        """, [instance_id, app_id, session_id, input_json, html])
    except Exception as lake_exc:
        log.warning(
            "DuckLake write failed for app instance %s — cross-session persistence broken: %s",
            instance_id, lake_exc,
        )


def _open_and_render(app_id: str, session_id: str, input_data: dict) -> tuple[str, str]:
    """Open an app, render its HTML, store in mcp_app_instances.
    Returns (instance_id, html)."""
    if not session_id:
        row = _con.execute("SELECT gen_random_uuid()::VARCHAR").fetchone()
        session_id = row[0] if row else "unknown"

    try:
        row = _con.execute(
            "SELECT open_app(?, ?, ?::JSON)",
            [app_id, session_id, json.dumps(input_data)],
        ).fetchone()
    except Exception as exc:
        return ("", f"<p>open_app failed: {exc}</p>")

    if not row or not row[0]:
        return ("", "<p>App not found</p>")

    dispatch = row[0]
    if isinstance(dispatch, str):
        try:
            dispatch = json.loads(dispatch)
        except Exception:
            pass

    instance_id = dispatch.get("instance_id", "") if isinstance(dispatch, dict) else ""
    html_field = dispatch.get("html", {}) if isinstance(dispatch, dict) else {}

    # Unwrap nested dispatch if html is also a JSON string
    if isinstance(html_field, str):
        try:
            html_field = json.loads(html_field)
        except Exception:
            pass

    # pending_render -> Python runtime handles base-template composition
    if isinstance(html_field, dict) and html_field.get("status") == "pending_render":
        html = _compose_and_render(app_id, input_data, instance_id)
    elif isinstance(html_field, str) and html_field.strip().startswith("<"):
        html = html_field  # already rendered HTML
    else:
        html = f"<pre>{json.dumps(dispatch, indent=2, default=str)}</pre>"

    if instance_id:
        _store_instance(instance_id, app_id, session_id, input_data, html)

    return (instance_id, html)


# ---------------------------------------------------------------------------
# MCP server builder
# ---------------------------------------------------------------------------

def build_mcp_server() -> FastMCP:
    instructions = ORG_SYSTEM_PROMPTS.get(OrgType.ORCHESTRATOR, "AgentFarmer orchestrator.")
    mcp = FastMCP(name="agent-farm", instructions=instructions)

    # --- PROMPTS ---

    @mcp.prompt(name="agent_farmer",
                description="AgentFarmer system prompt — orchestrator identity and instructions.")
    def _p_farmer() -> str:
        return ORG_SYSTEM_PROMPTS.get(OrgType.ORCHESTRATOR, "")

    for org_id, org_type in _ORG_MAP.items():
        def _make(ot=org_type, oi=org_id):
            @mcp.prompt(name=f"{oi}_org",
                        description=f"System prompt for {oi.capitalize()}Org.")
            def _p() -> str:
                return ORG_SYSTEM_PROMPTS.get(ot, "")
        _make()

    # --- RESOURCES ---

    @mcp.resource("agent-farm://orchestrator/tools_schema",
                  name="Orchestrator Tools Schema",
                  description="JSON schema of the 4 org dispatch tools.",
                  mime_type="application/json")
    def _r_schema() -> str:
        if _check_ready_now():
            return "[]"
        row = _con.execute("SELECT orchestrator_tools_schema()").fetchone()
        return str(row[0]) if row else "[]"

    @mcp.resource("agent-farm://orchestrator/dispatch_guide",
                  name="Dispatch Guide",
                  description="How to delegate tasks to orgs.",
                  mime_type="text/plain")
    def _r_guide() -> str:
        return (
            "AgentFarmer Dispatch Guide\n"
            "==========================\n\n"
            "  call_dev_org(task, session_id?)      — code, pipelines, tests, PRs\n"
            "  call_ops_org(task, session_id?)      — deployments, CI/CD, monitoring\n"
            "  call_research_org(task, session_id?) — web search, summaries, analysis\n"
            "  call_studio_org(task, session_id?)   — specs, briefings, roadmaps, assets\n\n"
            "Pass the same session_id across calls to group them into one session.\n"
            "Inspect state: query('SELECT * FROM lake_status()')\n"
        )

    @mcp.resource("agent-farm://orgs/{org_id}",
                  name="Org System Prompt",
                  description="System prompt for dev, ops, research, studio, or orchestrator.",
                  mime_type="text/plain")
    def _r_org(org_id: str) -> str:
        org_type = _ORG_MAP.get(org_id.lower())
        return ORG_SYSTEM_PROMPTS.get(org_type, f"Unknown org: {org_id}") if org_type else f"Unknown org: {org_id}"

    @mcp.resource("agent-farm://dashboard",
                  name="Agent Farm Dashboard",
                  description="Live HTML dashboard — rendered via open_app + minijinja.",
                  mime_type="text/html")
    def _r_dashboard() -> str:
        if _check_ready_now():
            return "<p>Server initializing…</p>"
        _, html = _open_and_render("app.dashboard", "system-dashboard", {})
        return html

    @mcp.resource("agent-farm://ui/{instance_id}",
                  name="App UI Instance",
                  description="Rendered HTML for a specific app instance (approval, choices, terminal, etc.).",
                  mime_type="text/html")
    def _r_app(instance_id: str) -> str:
        # Serve queued pre-bootstrap query UIs immediately.
        with _pending_queries_lock:
            if instance_id in _preboot_ui:
                return _preboot_ui[instance_id]
        if _check_ready_now():
            return "<p>Server initializing…</p>"
        # Try local session DB first
        try:
            row = _con.execute(
                "SELECT rendered_html FROM mcp_app_instances WHERE instance_id = ?",
                [instance_id],
            ).fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        # Fall back to DuckLake (instance may have been created in another session)
        try:
            row = _con.execute(
                "SELECT rendered_html FROM lake.mcp_app_instances WHERE instance_id = ?",
                [instance_id],
            ).fetchone()
            if row and row[0]:
                log.debug("Served app instance %s from DuckLake (cross-session)", instance_id)
                return row[0]
        except Exception as lake_exc:
            log.warning(
                "DuckLake lookup failed for instance %s: %s", instance_id, lake_exc
            )
        return f"<p>Instance not found: {instance_id}</p>"

    # --- TOOLS ---

    @mcp.tool(description=(
        "Delegate a coding, pipeline, or test task to DevOrg. "
        "DevOrg handles: code read/write, config creation, test runs, PR prep."
    ))
    def call_dev_org(task: str, session_id: str = "") -> CallToolResult:
        if err := _check_ready():
            return _tool_result(f"Error: {err}")
        return _tool_result(_dispatch("call_dev_org", task, session_id),
                            resource_uri="agent-farm://dashboard")

    @mcp.tool(description=(
        "Delegate a deployment, CI/CD, or infrastructure task to OpsOrg. "
        "OpsOrg handles: deployments (with approval), rollbacks, render jobs, monitoring."
    ))
    def call_ops_org(task: str, session_id: str = "") -> CallToolResult:
        if err := _check_ready():
            return _tool_result(f"Error: {err}")
        return _tool_result(_dispatch("call_ops_org", task, session_id),
                            resource_uri="agent-farm://dashboard")

    @mcp.tool(description=(
        "Delegate a web research or summarisation task to ResearchOrg. "
        "ResearchOrg handles: SearXNG searches, source summaries, document analysis."
    ))
    def call_research_org(task: str, session_id: str = "") -> CallToolResult:
        if err := _check_ready():
            return _tool_result(f"Error: {err}")
        return _tool_result(_dispatch("call_research_org", task, session_id),
                            resource_uri="agent-farm://dashboard")

    @mcp.tool(description=(
        "Delegate a spec, briefing, documentation, or asset task to StudioOrg. "
        "StudioOrg handles: requirements, user stories, briefings, roadmaps, asset indexing."
    ))
    def call_studio_org(task: str, session_id: str = "") -> CallToolResult:
        if err := _check_ready():
            return _tool_result(f"Error: {err}")
        return _tool_result(_dispatch("call_studio_org", task, session_id),
                            resource_uri="agent-farm://dashboard")

    @mcp.tool(description=(
        "Execute any SQL or macro against Agent Farm DuckDB — full access to all macros "
        "(base/tools/orgs/ui + spec/rag). "
        "Examples: query('SELECT * FROM lake_status()') | "
        "query('SELECT * FROM lake_notes()') | "
        "query('SELECT * FROM lake_approvals_pending()') | "
        "query(\"SELECT function_name FROM duckdb_functions() "
        "WHERE function_type='macro' ORDER BY 1\")"
    ))
    def query(sql: str) -> CallToolResult:
        # Avoid client tool-call timeouts during startup: return a UI URI immediately,
        # execute the query once bootstrap finishes.
        if _check_ready_now():
            iid = _queue_query(sql)
            _store_instance(iid, "query", "query", {"sql": sql}, _preboot_ui.get(iid, "<p>Server initializing…</p>"))
            return _tool_result(
                f"Queued — view at agent-farm://ui/{iid}",
                resource_uri=f"agent-farm://ui/{iid}",
            )
        if err := _check_ready():
            return _tool_result(f"Error: {err}")
        try:
            result = _con.execute(sql)
            if result is None:
                return _tool_result("(no result)")
            if not result.description:
                return _tool_result("(statement executed, no rows returned)")
            rows = result.fetchall()
            cols = [d[0] for d in result.description]
            # Single-cell result: check for pending actions or HTML render
            if len(rows) == 1 and len(cols) == 1:
                val = rows[0][0]
                # Pending DML action (notes_board_create, notes_board_update, …)
                handled = _handle_pending_action(val)
                if handled is not val:
                    return _tool_result(str(handled))
                # UI sentinel: open_app / render_app return {"status":"opened"|"pending_render", ...}
                # For these, we need to render HTML in Python runtime and return the ui:// resource URI.
                if isinstance(val, str):
                    try:
                        parsed = json.loads(val)
                    except Exception:
                        parsed = None
                else:
                    parsed = val if isinstance(val, dict) else None

                if isinstance(parsed, dict):
                    # open_app(...) returns status='opened' and includes {instance_id, app_id, session_id, input, html}
                    status = parsed.get("status")
                    if status == "opened" and "app_id" in parsed and "instance_id" in parsed:
                        iid = str(parsed.get("instance_id") or "")
                        if iid:
                            app_id = str(parsed.get("app_id"))
                            session_id = str(parsed.get("session_id") or "query")
                            input_data = parsed.get("input") if isinstance(parsed.get("input"), dict) else {}
                            html = _compose_and_render(app_id, input_data, iid)
                            _store_instance(iid, "query", session_id, input_data, html)
                            return _tool_result(
                                f"HTML output — view at agent-farm://ui/{iid}",
                                resource_uri=f"agent-farm://ui/{iid}",
                            )

                    # render_app(...) returns status='pending_render' and includes {app_id, instance_id, input}
                    if status == "pending_render" and "app_id" in parsed and "instance_id" in parsed:
                        iid = str(parsed.get("instance_id") or "")
                        if iid:
                            app_id = str(parsed.get("app_id"))
                            input_data = parsed.get("input") if isinstance(parsed.get("input"), dict) else {}
                            html = _compose_and_render(app_id, input_data, iid)
                            _store_instance(iid, "query", "query", input_data, html)
                            return _tool_result(
                                f"HTML output — view at agent-farm://ui/{iid}",
                                resource_uri=f"agent-farm://ui/{iid}",
                            )

                # HTML output → store as app instance, return resource URI
                if isinstance(val, str) and val.strip().startswith("<"):
                    import uuid as _uuid
                    iid = "qry-" + _uuid.uuid4().hex[:8]
                    _store_instance(iid, "query", "query", {"sql": sql}, val)
                    return _tool_result(
                        f"HTML output — view at agent-farm://ui/{iid}",
                        resource_uri=f"agent-farm://ui/{iid}",
                    )
            return _tool_result(_fmt_rows(rows, cols))
        except Exception as exc:
            return _tool_result(f"Error: {exc}")

    return mcp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_mcp_stdio_host(
    db_path: str,
    http_port: int | None = None,
    http_api_key: str | None = None,
) -> None:
    """Start the MCP stdio server immediately; bootstrap DuckDB in background."""
    # Launch bootstrap in background so MCP handshake is not delayed
    t = threading.Thread(
        target=_bootstrap_thread,
        args=(db_path, http_port, http_api_key),
        daemon=True,
        name="agent-farm-bootstrap",
    )
    t.start()

    mcp = build_mcp_server()
    log.info("MCP server starting — bootstrap running in background thread")
    mcp.run(transport="stdio")


