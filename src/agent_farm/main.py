"""
Agent Farm MCP Server - DuckDB-powered Spec Engine

The Agent Farm uses a DuckDB-based Spec Engine as the central "Spec-OS" for all agents.
The Spec Engine manages specifications for:
- Agents, skills, workflows
- APIs/protocols (HTTP/MCP/OpenAPI/GraphQL)
- JSON Schemas for validation
- Prompt/plan templates (MiniJinja)
- Task templates, UIs, Open-Responses

Entry point for the MCP server.
"""

import atexit
import json
import logging
import os
import re
import signal
import time
from contextlib import nullcontext
from pathlib import Path

import duckdb
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from .duckdb_utils import (
    connect_duckdb_persistent,
    has_non_comment_content,
    load_duckdb_extensions,
    split_sql_statements,
)
from .extensions import DUCKDB_EXTENSIONS
from .logging_config import setup_logging
from .schemas import AGENT_TABLES_SQL
from .spec_engine import get_spec_engine
from .startup_ui import suppress_stderr_info, use_startup_ui

log = logging.getLogger("agent_farm.main")

AGENT_FARM_DIR = Path.home() / ".agent_farm"
DEFAULT_DB_PATH = str(AGENT_FARM_DIR / "agent_farm.db")
# MCP stdio: separate file by default so REPL (`agent_farm.db`) does not hold a DuckDB lock.
DEFAULT_MCP_DB_PATH = str(AGENT_FARM_DIR / "agent_farm_mcp.db")
# DuckLake shared catalog: cross-process tables (notes_board, shared agent sessions, ...).
# Attach via: ATTACH '<path>' AS lake (TYPE DUCKLAKE)
# Both REPL and MCP attach this catalog for shared persistent state.
DUCKLAKE_CATALOG_PATH = str(AGENT_FARM_DIR / "lake.db")
MCP_PID_FILE = AGENT_FARM_DIR / "mcp.pid"


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _kill_process(pid: int, timeout: float = 5.0) -> bool:
    """Kill a process and wait for it to die. Returns True if process is gone."""
    try:
        if os.name == "nt":
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=timeout,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _is_process_alive(pid):
                return True
            time.sleep(0.3)
        return not _is_process_alive(pid)
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        return True


def ensure_single_mcp_instance() -> None:
    """Ensure only one MCP server instance runs at a time.

    Reads ~/.agent_farm/mcp.pid. If the PID is still alive, kills it and waits
    for file locks to be released. Writes own PID and registers atexit cleanup.
    """
    AGENT_FARM_DIR.mkdir(parents=True, exist_ok=True)

    if MCP_PID_FILE.exists():
        try:
            old_pid = int(MCP_PID_FILE.read_text().strip())
        except (ValueError, OSError):
            old_pid = None

        if old_pid and old_pid != os.getpid() and _is_process_alive(old_pid):
            log.info("Killing stale MCP server (PID %d)", old_pid)
            if _kill_process(old_pid):
                log.info("Stale MCP server (PID %d) terminated", old_pid)
                time.sleep(1)  # let Windows release file handles
            else:
                log.warning("Could not kill stale MCP server (PID %d)", old_pid)

    # Write own PID
    try:
        MCP_PID_FILE.write_text(str(os.getpid()))
    except OSError as exc:
        log.warning("Could not write PID file: %s", exc)

    def _cleanup_pid():
        try:
            if MCP_PID_FILE.exists() and MCP_PID_FILE.read_text().strip() == str(os.getpid()):
                MCP_PID_FILE.unlink()
        except OSError:
            pass

    atexit.register(_cleanup_pid)


def cleanup_stale_files() -> None:
    """Remove orphaned session DBs, WAL files, and broken WAL backups."""
    sessions_dir = AGENT_FARM_DIR / "sessions"
    if not sessions_dir.exists():
        return
    removed = 0
    for pattern in ["mcp_*.db", "mcp_*.db.wal"]:
        for stale in sessions_dir.glob(pattern):
            try:
                stale.unlink()
                removed += 1
            except OSError:
                pass  # still locked by current session — skip
    # Broken WAL backups in main dir
    for broken_wal in AGENT_FARM_DIR.glob("*.wal.broken.*"):
        try:
            broken_wal.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        log.info("Cleaned up %d stale/orphaned file(s)", removed)


def resolve_mcp_database_path(explicit: str | None) -> str:
    """Path for `agent-farm mcp`.

    Priority:
      1. explicit --db flag
      2. DUCKDB_DATABASE env var
      3. DEFAULT_MCP_DB_PATH — persistent per-installation DB

    Multiple concurrent MCP sessions:
      DuckDB allows only one writer per file. bootstrap_db() retries the lock
      up to 8× (16s total). If still locked, it falls back to a per-session file
      under ~/.agent_farm/sessions/mcp_{pid}_{ts}.db automatically.
      Shared cross-session state (notes, user profile, approvals, app instances)
      lives in DuckLake (lake.db) and is attached on every bootstrap — regardless
      of which DB file the session uses.
    """
    if explicit:
        return explicit
    return os.environ.get("DUCKDB_DATABASE") or DEFAULT_MCP_DB_PATH

_connection_cache: dict[str, duckdb.DuckDBPyConnection] = {}


def find_mcp_config() -> list[tuple[str, dict]]:
    """
    Discover MCP configuration files in standard locations.
    Returns list of (config_path, config_data) tuples.
    """
    config_locations = [
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
        Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        Path.home() / ".mcp" / "config.json",
    ]

    found_configs = []
    for config_path in config_locations:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8-sig") as f:
                    config_data = json.load(f)
                found_configs.append((str(config_path), config_data))
                log.info("Found MCP config: %s", config_path)
            except Exception as e:
                log.error("Error reading %s: %s", config_path, e)

    return found_configs


def extract_mcp_servers(configs: list[tuple[str, dict]]) -> dict:
    """
    Extract MCP server definitions from config files.
    Returns dict of server_name -> server_config
    """
    servers = {}
    for config_path, config_data in configs:
        if "mcpServers" in config_data:
            for name, server_config in config_data["mcpServers"].items():
                servers[name] = {"source": config_path, **server_config}
        elif "servers" in config_data:
            for name, server_config in config_data["servers"].items():
                servers[name] = {"source": config_path, **server_config}
    return servers


def _is_agent_farm_self_mcp_entry(server_config: dict) -> bool:
    """True if this entry runs Agent Farm as the MCP server (inventory should not list ourselves)."""
    args = server_config.get("args") or []
    if not isinstance(args, (list, tuple)):
        return False
    flat = " ".join(str(a) for a in args).lower()
    if "mcp" not in flat:
        return False
    return "agent-farm" in flat or "agent_farm" in flat or "-m agent_farm" in flat


def filter_external_mcp_servers(servers: dict) -> dict:
    """
    Drop entries that point at this package's MCP server so mcp_servers is only *other* servers.
    Set AGENT_FARM_MCP_INVENTORY_INCLUDE_SELF=1 to disable (debug).
    """
    if os.environ.get("AGENT_FARM_MCP_INVENTORY_INCLUDE_SELF", "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return dict(servers)
    return {k: v for k, v in servers.items() if not _is_agent_farm_self_mcp_entry(v)}


def setup_mcp_tables(con: duckdb.DuckDBPyConnection, servers: dict) -> None:
    """
    Create tables with discovered MCP server info for SQL access.
    """
    con.sql("""
        CREATE OR REPLACE TABLE mcp_servers (
            name VARCHAR,
            command VARCHAR,
            args VARCHAR[],
            env JSON,
            source_config VARCHAR
        )
    """)

    for name, config in servers.items():
        command = config.get("command", "")
        args = config.get("args", [])
        env = json.dumps(config.get("env", {}))
        source = config.get("source", "")

        con.execute(
            "INSERT INTO mcp_servers VALUES (?, ?, ?, ?, ?)",
            [name, command, args, env, source],
        )

    log.info("Registered %d external MCP server(s) in mcp_servers table", len(servers))


def load_core_extensions(
    con: duckdb.DuckDBPyConnection,
    *,
    progress: Progress | None = None,
    task_id: TaskID | None = None,
) -> tuple[list[str], list[str]]:
    """Load DuckDB extensions (Spec Engine + extras). Returns (loaded, skipped_optional)."""
    return load_duckdb_extensions(con, DUCKDB_EXTENSIONS, progress=progress, task_id=task_id)


def migrate_mcp_apps_sep_columns(con: duckdb.DuckDBPyConnection) -> None:
    """Add SEP-1865 columns to legacy mcp_apps (must run before ui.sql defines views using them)."""
    try:
        rows = con.execute("SELECT name FROM pragma_table_info('mcp_apps')").fetchall()
    except Exception:
        return
    if not rows:
        return
    names = {r[0] for r in rows}
    if "resource_uri" not in names:
        con.execute("ALTER TABLE mcp_apps ADD COLUMN resource_uri VARCHAR")
    if "mime_type" not in names:
        con.execute(
            "ALTER TABLE mcp_apps ADD COLUMN mime_type VARCHAR DEFAULT 'text/html;profile=mcp-app'"
        )
    if "ui_meta" not in names:
        con.execute("ALTER TABLE mcp_apps ADD COLUMN ui_meta JSON")


def ensure_mcp_apps_sep_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Upgrade existing DBs: SEP columns + backfill ui:// URIs and CSP metadata."""
    migrate_mcp_apps_sep_columns(con)
    con.execute("""
        UPDATE mcp_apps SET
            resource_uri = COALESCE(resource_uri, 'ui://agent-farm/app/' || id),
            mime_type = CASE
                WHEN mime_type IS NULL OR trim(mime_type) = '' THEN 'text/html;profile=mcp-app'
                ELSE mime_type END,
            ui_meta = COALESCE(
                ui_meta,
                '{"ui":{"csp":{"resourceDomains":["https://cdn.tailwindcss.com"],"connectDomains":[]},"prefersBorder":true}}'::JSON
            )
    """)


def create_runtime_tables(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create runtime tables for session management, auditing, and approvals.
    These are operational tables, not specifications (specs live in spec_objects).
    """
    con.sql("""
        -- Sequences
        CREATE SEQUENCE IF NOT EXISTS audit_seq START 1;
        CREATE SEQUENCE IF NOT EXISTS approval_seq START 1;
        CREATE SEQUENCE IF NOT EXISTS org_call_seq START 1;
        CREATE SEQUENCE IF NOT EXISTS radio_message_seq START 1;

        -- Audit log for all agent actions
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY DEFAULT nextval('audit_seq'),
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP DEFAULT now(),
            entry_type VARCHAR NOT NULL,  -- 'tool_call', 'spec_access', 'feedback', 'learning'
            spec_id INTEGER,              -- Reference to spec_objects if relevant
            tool_name VARCHAR,
            parameters JSON,
            result JSON,
            decision VARCHAR,             -- 'allowed', 'denied', 'approved', 'rejected'
            violations VARCHAR[]
        );

        -- Session state for active agent sessions
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,             -- Optional runtime agent identifier
            started_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'active',
            context JSON DEFAULT '{}',    -- Session context/state
            messages JSON DEFAULT '[]'
        );

        -- Pending approvals for sensitive operations
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id INTEGER PRIMARY KEY DEFAULT nextval('approval_seq'),
            session_id VARCHAR NOT NULL,
            spec_id INTEGER,              -- Reference to spec_objects
            tool_name VARCHAR NOT NULL,
            tool_params JSON,
            reason VARCHAR,
            created_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'pending',
            decision VARCHAR,
            resolved_at TIMESTAMP,
            resolved_by VARCHAR
        );

        -- Persistent radio channels and messages
        CREATE TABLE IF NOT EXISTS radio_subscriptions (
            sub_id VARCHAR PRIMARY KEY,
            org_id VARCHAR,
            channel_name VARCHAR NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS radio_messages (
            id INTEGER PRIMARY KEY DEFAULT nextval('radio_message_seq'),
            channel_name VARCHAR NOT NULL,
            payload JSON NOT NULL,
            created_at TIMESTAMP DEFAULT now()
        );

        -- Inter-organization calls (for swarm coordination)
        CREATE TABLE IF NOT EXISTS org_calls (
            id INTEGER PRIMARY KEY DEFAULT nextval('org_call_seq'),
            session_id VARCHAR NOT NULL,
            caller_org VARCHAR NOT NULL,
            target_org VARCHAR NOT NULL,
            task VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'pending',
            result JSON,
            created_at TIMESTAMP DEFAULT now(),
            completed_at TIMESTAMP
        );

        -- Notes board for collaboration
        CREATE TABLE IF NOT EXISTS notes_board (
            id VARCHAR PRIMARY KEY,
            project VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content VARCHAR,
            note_type VARCHAR DEFAULT 'general',
            status VARCHAR DEFAULT 'open',
            created_by VARCHAR DEFAULT 'system',
            spec_refs JSON DEFAULT '[]',  -- References to related specs
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)
    log.info("Runtime tables created.")


SQL_LOAD_ORDER = [
    "base.sql",
    "ollama.sql",
    "tools.sql",
    "agent.sql",
    "harness.sql",
    "orgs.sql",
    "org_tools.sql",
    "ui.sql",
    "extensions.sql",
    "ducklake.sql",   # DuckLake shared catalog macros (skipped if lake not attached)
]

# Spec Engine extension macros — live in sql/spec/ subdirectory.
# Loaded AFTER main SQL macros because they depend on spec_objects table
# (created by get_spec_engine) and may reference main macros.
SPEC_SQL_LOAD_ORDER = [
    "macros.sql",   # spec_render, spec_validate, spec_get, mcp_list_remote, …
    "rag.sql",      # vss_search_*, hybrid_search_*, rag_relevant_specs, …
]


def load_sql_macros(con: duckdb.DuckDBPyConnection, *, quiet: bool = False) -> int:
    """Load SQL macros from the sql/ directory (and sql/spec/ subdirectory).

    Load order:
      1. Top-level sql/*.sql in SQL_LOAD_ORDER, then remaining alphabetically.
      2. sql/spec/*.sql in SPEC_SQL_LOAD_ORDER, then remaining alphabetically.
         (Spec macros depend on spec_objects table from get_spec_engine.)

    Returns total number of statements executed (macros + DDL).
    """
    _info = log.debug if quiet else log.info
    sql_dir = os.path.join(os.path.dirname(__file__), "sql")
    total_loaded = 0
    errors: list[str] = []

    def _load_file(sql_path: str, label: str) -> int:
        """Execute all statements in a SQL file, return count."""
        with open(sql_path, "r", encoding="utf-8") as fh:
            sql_script = fh.read()
        statements = split_sql_statements(sql_script)
        n = 0
        for stmt in statements:
            if not has_non_comment_content(stmt):
                continue
            try:
                con.sql(stmt)
                n += 1
            except Exception as e:
                errors.append(f"{label}: {e}")
        return n

    if not os.path.isdir(sql_dir):
        log.warning("sql/ directory not found, no macros loaded")
        return 0

    migrate_mcp_apps_sep_columns(con)

    # ── Top-level sql/*.sql ───────────────────────────────────────────────────
    all_top = [f for f in os.listdir(sql_dir) if f.endswith(".sql") and not f.startswith(".")]
    top_ordered = [f for f in SQL_LOAD_ORDER if f in all_top]

    # DuckLake is required — ducklake.sql should always load.
    # If lake.notes_board is inaccessible here, it means setup_ducklake_catalog failed;
    # log loudly so the failure is visible, but still attempt to load ducklake.sql
    # (the macro CREATE OR REPLACE statements are lazy — they fail at call time, not definition time).
    try:
        con.execute("SELECT 1 FROM lake.notes_board LIMIT 0")
    except Exception as _lake_check_err:
        log.error(
            "lake.notes_board not accessible before loading ducklake.sql — "
            "DuckLake catalog may not be attached. "
            "Shared persistence will be broken. Error: %s",
            _lake_check_err,
        )

    top_ordered += sorted(f for f in all_top if f not in SQL_LOAD_ORDER)
    for sql_file in top_ordered:
        n = _load_file(os.path.join(sql_dir, sql_file), sql_file)
        total_loaded += n
        _info("Loaded %d statements from %s", n, sql_file)

    # ── sql/spec/*.sql — Spec Engine extension macros ─────────────────────────
    spec_dir = os.path.join(sql_dir, "spec")
    if os.path.isdir(spec_dir):
        all_spec = [f for f in os.listdir(spec_dir) if f.endswith(".sql") and not f.startswith(".")]
        spec_ordered = [f for f in SPEC_SQL_LOAD_ORDER if f in all_spec]
        spec_ordered += sorted(f for f in all_spec if f not in SPEC_SQL_LOAD_ORDER)
        for sql_file in spec_ordered:
            label = f"spec/{sql_file}"
            n = _load_file(os.path.join(spec_dir, sql_file), label)
            total_loaded += n
            _info("Loaded %d statements from %s", n, label)
    else:
        log.debug("sql/spec/ directory not found, skipping spec macros")

    if errors:
        # Log all errors but only raise if there were critical failures
        for err in errors[:30]:
            log.warning("SQL load warning: %s", err)

    return total_loaded


def create_agent_tables(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create agent infrastructure tables (workspaces, security_policy, etc.).
    These must exist before SQL macros are loaded, as macros reference them.
    """
    for stmt in split_sql_statements(AGENT_TABLES_SQL):
        stmt = stmt.strip()
        if stmt and has_non_comment_content(stmt):
            try:
                con.sql(stmt)
            except Exception as e:
                log.error("Error creating agent table: %s", e)
    log.info("Agent infrastructure tables created.")


def seed_macros_to_spec_engine(con: duckdb.DuckDBPyConnection) -> int:
    """
    Parse all SQL macro files and insert each macro as a kind='macro' spec object.
    Idempotent: skips macros already present (matched by name + kind).
    Returns the number of newly seeded macros.
    """
    engine = get_spec_engine(con)
    sql_dir = Path(__file__).parent / "sql"

    category_map = {
        "base": "Utilities",
        "ollama": "LLM & Embeddings",
        "tools": "Web / Shell / Files / Git",
        "agent": "Security & Approval",
        "harness": "Agent Harness & Routing",
        "orgs": "Organizations & Orchestration",
        "org_tools": "Org Operations",
        "ui": "MCP Apps & UI",
        "extensions": "Advanced Extensions",
        "macros": "Spec Engine",
        "rag": "RAG & Vector Search",
    }

    existing: set[str] = set()
    try:
        rows = con.execute("SELECT name FROM spec_objects WHERE kind = 'macro'").fetchall()
        existing = {r[0] for r in rows}
    except Exception:
        pass

    macro_header_re = re.compile(
        r"CREATE OR REPLACE MACRO\s+(\w+)\s*\(([^)]*)\)", re.IGNORECASE | re.DOTALL
    )

    seeded = 0
    for sql_file in sql_dir.rglob("*.sql"):
        category = category_map.get(sql_file.stem, sql_file.stem)
        text = sql_file.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        offsets: list[int] = []
        pos = 0
        for ln in lines:
            offsets.append(pos)
            pos += len(ln) + 1

        for m in macro_header_re.finditer(text):
            name = m.group(1)
            args = ", ".join(a.strip() for a in m.group(2).split(",") if a.strip())
            signature = f"{name}({args})"

            if name in existing:
                continue

            match_pos = m.start()
            line_idx = next(
                (i for i in range(len(offsets) - 1, -1, -1) if offsets[i] <= match_pos),
                0,
            )

            description_lines = []
            j = line_idx - 1
            while j >= 0 and lines[j].strip().startswith("--"):
                description_lines.insert(0, lines[j].strip().lstrip("-").strip())
                j -= 1
            description = " ".join(description_lines) if description_lines else f"{category} macro"

            try:
                engine.spec_create(
                    kind="macro",
                    name=name,
                    summary=description,
                    version="1.0.0",
                    status="active",
                    doc=(
                        f"```sql\nSELECT {signature};\n```\n\n"
                        f"**Category:** {category}  \n**File:** `{sql_file.name}`"
                    ),
                    payload={
                        "signature": signature,
                        "args": args,
                        "category": category,
                        "file": sql_file.name,
                    },
                )
                existing.add(name)
                seeded += 1
            except Exception as e:
                log.warning("Skipping macro %s: %s", name, e)

    return seeded




def setup_ducklake_catalog(con: duckdb.DuckDBPyConnection) -> bool:
    """Attach the shared DuckLake catalog and ensure all cross-process tables exist.

    DuckLake is REQUIRED infrastructure — all shared persistent state lives here:
      lake.notes_board         — project notes
      lake.shared_sessions     — agent sessions visible to all processes
      lake.shared_org_calls    — inter-org call log
      lake.mcp_app_instances   — rendered HTML (survives MCP reconnects)
      lake.pending_approvals   — approval decisions (survive MCP restarts)
      lake.user_profile        — user settings

    Multiple processes can attach the same DuckLake catalog concurrently (MVCC).
    The ducklake extension is required (True in DUCKDB_EXTENSIONS) so it will
    always be loaded before this function is called.

    Returns True on success. Logs errors loudly and returns False only if the catalog
    cannot be attached/initialized (to allow callers to surface the failure).
    """
    from .duckdb_utils import is_extension_loaded

    if not is_extension_loaded(con, "ducklake"):
        log.error(
            "DuckLake extension is NOT loaded but is marked required — "
            "shared persistent state will not work! "
            "Check that ducklake was installed successfully."
        )
        return False

    catalog_path = str(Path(DUCKLAKE_CATALOG_PATH).resolve())
    data_dir = str(AGENT_FARM_DIR / "lake_data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    try:
        # Attach DuckLake catalog. Idempotent via try/except on re-attach.
        con.execute(
            f"ATTACH '{catalog_path}' AS lake (TYPE DUCKLAKE, DATA_PATH '{data_dir}')"
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "already attached" in msg or "already open" in msg or "unique file handle" in msg:
            log.debug("DuckLake catalog already attached.")
        else:
            log.error(
                "DuckLake catalog ATTACH FAILED: %s  "
                "Path: %s  "
                "Shared persistent state (notes, sessions, approvals) will not work!",
                exc, catalog_path,
            )
            return False

    try:
        # Shared cross-process tables in DuckLake
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.notes_board (
                id VARCHAR NOT NULL,
                project VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                content VARCHAR,
                note_type VARCHAR DEFAULT 'general',
                status VARCHAR DEFAULT 'open',
                created_by VARCHAR DEFAULT 'system',
                spec_refs JSON DEFAULT '[]',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.shared_sessions (
                id VARCHAR NOT NULL,
                agent_id VARCHAR,
                process_type VARCHAR DEFAULT 'unknown',  -- 'repl' | 'mcp'
                started_at TIMESTAMP,
                status VARCHAR DEFAULT 'active',
                context JSON DEFAULT '{}'
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.shared_org_calls (
                id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                caller_org VARCHAR NOT NULL,
                target_org VARCHAR NOT NULL,
                task VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'pending',
                result JSON,
                created_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        # Persistent app instances — HTML renders survive MCP reconnects + visible to all sessions
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.mcp_app_instances (
                instance_id VARCHAR NOT NULL,
                app_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'active',
                input_data JSON,
                rendered_html TEXT,
                created_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        # Persistent approvals — decisions survive MCP restarts
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.pending_approvals (
                id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                spec_id VARCHAR,
                tool_name VARCHAR NOT NULL,
                tool_params JSON,
                reason VARCHAR,
                status VARCHAR DEFAULT 'pending',
                decision VARCHAR,
                resolved_by VARCHAR,
                created_at TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        # Migration: add spec_id to existing lake.pending_approvals tables.
        # DuckLake tables are not in information_schema; use DESCRIBE instead.
        try:
            col_rows = con.execute("DESCRIBE lake.pending_approvals").fetchall()
            existing_cols = {r[0] for r in col_rows}
            if "spec_id" not in existing_cols:
                con.execute("ALTER TABLE lake.pending_approvals ADD COLUMN spec_id VARCHAR")
                log.info("Migrated lake.pending_approvals: added spec_id column")
        except Exception as _alt_exc:
            log.debug("spec_id migration skipped (table new or ALTER unsupported): %s", _alt_exc)
        # User profile — persists across all sessions
        con.execute("""
            CREATE TABLE IF NOT EXISTS lake.user_profile (
                user_id VARCHAR NOT NULL,
                profile_id VARCHAR,
                custom_settings JSON,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        log.info(
            "DuckLake shared catalog ready: %s  "
            "(notes_board, shared_sessions, shared_org_calls, mcp_app_instances, "
            "pending_approvals, user_profile)",
            catalog_path,
        )
        return True
    except Exception as exc:
        log.warning("DuckLake table creation failed: %s", exc)
        return False
def bootstrap_db(
    db_path: str,
    *,
    interactive_ui: bool | None = None,
) -> duckdb.DuckDBPyConnection:
    """
    Canonical bootstrap for Agent Farm. Creates and fully initializes a DuckDB connection.

    Initialization order:
    1. Connect to DuckDB
    2. Load extensions (full list: required + optional best-effort)
    3. Initialize Spec Engine (schema + UDFs)
    4. Discover MCP configurations
    5. Register Python UDFs
    6. Create agent infrastructure tables
    7. Create runtime tables
    8. Load SQL macros
    9. Seed org configs
    10. Seed macros into Spec Engine (self-knowledge)
    11. Populate loaded_extensions table

    interactive_ui: If True, Rich progress on stderr and brief emoji lines; file log stays detailed.
        If None, enabled when stderr is a TTY and AGENT_FARM_PLAIN_LOG is unset.
    """
    if interactive_ui is None:
        interactive_ui = use_startup_ui()

    AGENT_FARM_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging(log_file=str(AGENT_FARM_DIR / "agent_farm.log"))

    cache_key = str(Path(db_path).resolve()) if db_path != ":memory:" else ":memory:"
    if cache_key in _connection_cache:
        con = _connection_cache[cache_key]
        try:
            con.execute("SELECT 1").fetchone()
            return con
        except Exception:
            del _connection_cache[cache_key]

    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    actual_db_path = db_path  # may be updated below if we fall back to session file
    for attempt in range(8):
        try:
            con = connect_duckdb_persistent(actual_db_path)
            break
        except Exception as e:
            msg = str(e).lower()
            is_lock = (
                "cannot open file" in msg
                or "already open" in msg
                or "used by" in msg
                or "another process" in msg
                or "in use" in msg
                or "prozess" in msg
                or "verwendet" in msg
                or "io error" in msg
            )
            if is_lock:
                if attempt < 7:
                    log.warning("Database locked (attempt %d/8), retrying in 2s: %s", attempt + 1, e)
                    time.sleep(2)
                else:
                    # Fall back to a per-session file so this session can still run.
                    # Shared persistent state lives in DuckLake (lake.db) regardless.
                    sessions_dir = AGENT_FARM_DIR / "sessions"
                    sessions_dir.mkdir(parents=True, exist_ok=True)
                    actual_db_path = str(
                        sessions_dir / f"mcp_{os.getpid()}_{int(time.time())}.db"
                    )
                    log.warning(
                        "DB file locked after 8 retries — falling back to per-session DB: %s  "
                        "(shared state via DuckLake lake.db)",
                        actual_db_path,
                    )
                    try:
                        con = connect_duckdb_persistent(actual_db_path)
                        break
                    except Exception as e2:
                        raise RuntimeError(
                            f"Could not open session DB either: {actual_db_path}\nOriginal error: {e}\nSession error: {e2}"
                        ) from e2
            else:
                raise

    # Cache under the path actually opened (may differ from requested if lock-fallback occurred)
    actual_cache_key = str(Path(actual_db_path).resolve()) if actual_db_path != ":memory:" else ":memory:"
    if actual_cache_key != cache_key:
        log.info("Session using fallback DB; cache key updated to %s", actual_cache_key)
    _connection_cache[actual_cache_key] = con
    log.info("Initializing Agent Farm (db: %s)...", actual_db_path)

    ui: Console | None = Console(stderr=True, highlight=False) if interactive_ui else None
    if ui:
        ui.print()
        ui.print(f"[bold green]🚜 Agent Farm[/]  [dim]{actual_db_path}[/]")

    with suppress_stderr_info() if interactive_ui else nullcontext():
        if interactive_ui and ui:
            with Progress(
                SpinnerColumn(style="green"),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=32),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=ui,
                transient=False,
            ) as progress:
                ext_task = progress.add_task(
                    "[cyan]DuckDB extensions[/]",
                    total=len(DUCKDB_EXTENSIONS),
                )
                loaded_extensions, skipped_ext = load_core_extensions(
                    con, progress=progress, task_id=ext_task
                )
            if skipped_ext:
                ui.print(
                    f"[yellow]⚠[/] Optional extensions skipped (Windows/build): "
                    f"[dim]{', '.join(skipped_ext)}[/]"
                )
        else:
            log.info("Loading extensions...")
            loaded_extensions, skipped_ext = load_core_extensions(con)
            # skipped_ext already logged once in load_duckdb_extensions

        log.info("Initializing Spec Engine...")
        try:
            from .spec_engine import get_spec_engine, register_spec_engine_tools

            if interactive_ui and ui:
                with ui.status("[bold cyan]📦 Spec Engine[/]  schema · macros · seed", spinner="dots"):
                    get_spec_engine(con, quiet=True)
                    spec_tools = register_spec_engine_tools(con)
                ui.print(f"[green]✓[/] Spec Engine + [bold]{len(spec_tools)}[/] tool UDFs")
            else:
                get_spec_engine(con)
                spec_tools = register_spec_engine_tools(con)
                log.info("Spec Engine: Registered %d UDFs", len(spec_tools))
        except ImportError as e:
            log.error("Spec Engine module not available: %s", e)
        except Exception as e:
            log.error("Error initializing Spec Engine: %s", e)

        log.info("Discovering MCP configurations...")
        mcp_configs = find_mcp_config()
        raw_mcp = extract_mcp_servers(mcp_configs)
        mcp_servers = filter_external_mcp_servers(raw_mcp)
        if mcp_servers:
            setup_mcp_tables(con, mcp_servers)
            if interactive_ui and ui:
                ui.print(
                    f"[green]✓[/] MCP inventory: [bold]{len(mcp_servers)}[/] other server(s) in [dim]mcp_servers[/]"
                )
        elif raw_mcp:
            setup_mcp_tables(con, {})
            log.info(
                "MCP config lists only Agent Farm (self); skipped for mcp_servers — add other servers to the same file"
            )
            if interactive_ui and ui:
                ui.print("[dim]— MCP config has no other servers (Agent Farm self excluded)[/]")
        else:
            log.info("No MCP configurations found")
            if interactive_ui and ui:
                ui.print("[dim]— No external MCP configs in standard paths[/]")
            con.sql("""
                CREATE OR REPLACE TABLE mcp_servers (
                    name VARCHAR, command VARCHAR, args VARCHAR[], env JSON, source_config VARCHAR
                )
            """)

        try:
            from .udfs import register_udfs

            registered = register_udfs(con)
            log.info("Registered %d UDFs: %s", len(registered), ", ".join(registered))
            if interactive_ui and ui:
                preview = ", ".join(registered[:5])
                more = f"… +{len(registered) - 5}" if len(registered) > 5 else ""
                ui.print(f"[green]✓[/] Python UDFs ([bold]{len(registered)}[/]): [dim]{preview}{more}[/]")
        except ImportError:
            log.info("UDFs module not available, skipping")
        except Exception as e:
            log.error("Error registering UDFs: %s", e)

        log.info("Creating agent infrastructure tables...")
        create_agent_tables(con)
        log.info("Creating runtime tables...")
        create_runtime_tables(con)
        ducklake_active = setup_ducklake_catalog(con)
        if ducklake_active:
            log.info(
                "DuckLake shared catalog: active — 6 shared tables "
                "(notes_board, shared_sessions, shared_org_calls, "
                "mcp_app_instances, pending_approvals, user_profile)"
            )
        if interactive_ui and ui:
            ui.print("[green]✓[/] Runtime + agent tables")

        log.info("Loading SQL macros...")
        if interactive_ui and ui:
            with ui.status("[bold cyan]📜 SQL macros[/]  base · tools · orgs · ui · spec …", spinner="line"):
                total_macros = load_sql_macros(con, quiet=True)
            ui.print(f"[green]✓[/] [bold]{total_macros}[/] SQL macros loaded (incl. spec/)")
        else:
            total_macros = load_sql_macros(con)
            log.info("Total: %d macros loaded.", total_macros)

        ensure_mcp_apps_sep_schema(con)

        try:
            from .orgs import generate_org_seed_sql

            for stmt in split_sql_statements(generate_org_seed_sql()):
                stmt = stmt.strip()
                if stmt and has_non_comment_content(stmt):
                    try:
                        con.sql(stmt)
                    except Exception as e:
                        log.error("Error seeding org: %s", e)
            log.info("Organization configs seeded.")
            if interactive_ui and ui:
                ui.print("[green]✓[/] Organization configs")
        except ImportError:
            log.info("Orgs module not available, skipping seed")
        except Exception as e:
            log.error("Error seeding orgs: %s", e)

        try:
            seeded = seed_macros_to_spec_engine(con)
            if seeded:
                log.info("Seeded %d macros into Spec Engine.", seeded)
                if interactive_ui and ui:
                    ui.print(f"[green]✓[/] Seeded [bold]{seeded}[/] macro specs into Spec Engine")
            else:
                log.info("Macro specs already up to date.")
                if interactive_ui and ui:
                    ui.print("[dim]— Macro specs already up to date[/]")
        except Exception as e:
            log.warning("Macro seeding failed: %s", e)

    if interactive_ui and ui:
        ui.print()

    con.sql(f"""
        CREATE OR REPLACE TABLE loaded_extensions AS
        SELECT unnest({loaded_extensions!r}::VARCHAR[]) as extension_name
    """)

    return con


def main():
    """Standalone MCP server entry (stdio). Prefer `agent-farm mcp` via CLI."""
    from .mcp_host import run_mcp_stdio_host

    AGENT_FARM_DIR.mkdir(parents=True, exist_ok=True)

    db_path = resolve_mcp_database_path(None)
    http_port = os.environ.get("SPEC_ENGINE_HTTP_PORT")
    http_api_key = os.environ.get("SPEC_ENGINE_API_KEY")
    port = int(http_port) if http_port else None
    run_mcp_stdio_host(db_path, http_port=port, http_api_key=http_api_key)


if __name__ == "__main__":
    main()
