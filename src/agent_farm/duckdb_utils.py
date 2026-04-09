"""Shared DuckDB helpers for Agent Farm runtime setup."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

import duckdb
from rich.progress import Progress, TaskID

from .extensions import ExtensionSpec

log = logging.getLogger("agent_farm.duckdb_utils")

# Per DuckDB docs / extension pages: install these from the community repo first
# (INSTALL x FROM community; or install_extension(x, repository="community")).
# httpserver is community-only per duckdb.org/community_extensions/extensions/httpserver.html
EXTENSION_COMMUNITY_REPO_FIRST: frozenset[str] = frozenset(
    {"duckdb_mcp", "http_client", "httpserver", "minijinja", "jsonata"}
)

# Extensions that live exclusively in the official DuckDB repo (extensions.duckdb.org).
# Community install attempt is skipped for these -- it would fail with "already installed
# from a different origin" and is never correct for core-shipped extensions.
EXTENSION_CORE_ONLY: frozenset[str] = frozenset(
    {"ducklake", "vss", "fts", "icu", "json", "lsh", "shellfs", "zipfs", "fts", "spatial"}
)


def has_non_comment_content(stmt: str) -> bool:
    """Check if a SQL statement has any non-comment content."""
    for ln in stmt.split("\n"):
        ln = ln.strip()
        if ln and not ln.startswith("--"):
            return True
    return False


def split_sql_statements(sql_content: str) -> list[str]:
    """Split SQL content into statements, respecting string literals and -- line comments."""
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    string_char = None

    i = 0
    while i < len(sql_content):
        char = sql_content[i]

        # Line comment: do not treat ' or " inside as string delimiters
        if not in_string and char == "-" and i + 1 < len(sql_content) and sql_content[i + 1] == "-":
            current.append(char)
            current.append(sql_content[i + 1])
            i += 2
            while i < len(sql_content) and sql_content[i] != "\n":
                current.append(sql_content[i])
                i += 1
            if i < len(sql_content):
                current.append("\n")
                i += 1
            continue

        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            current.append(char)
        elif char == string_char and in_string:
            if i + 1 < len(sql_content) and sql_content[i + 1] == string_char:
                current.append(char)
                current.append(char)
                i += 1
            else:
                in_string = False
                string_char = None
                current.append(char)
        elif char == ";" and not in_string:
            stmt = "".join(current).strip()
            if stmt and has_non_comment_content(stmt):
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    if current:
        stmt = "".join(current).strip()
        if stmt and has_non_comment_content(stmt):
            statements.append(stmt)

    return statements


def is_extension_loaded(con: duckdb.DuckDBPyConnection, extension_name: str) -> bool:
    """Return whether a DuckDB extension is currently loaded."""
    try:
        result = con.execute(
            """
            SELECT loaded
            FROM duckdb_extensions()
            WHERE extension_name = ?
            """,
            [extension_name],
        ).fetchone()
    except Exception:
        return False
    return bool(result and result[0])


def _install_and_load_extension(
    con: duckdb.DuckDBPyConnection,
    extension_name: str,
    *,
    repository: str | None,
    load_only: bool,
) -> None:
    """Official DuckDB Python pattern (duckdb.org docs): install_extension + load_extension.

    Uses the Python client API:
      con.install_extension(name)                    -- core/official repo
      con.install_extension(name, repository=...)    -- specific repo
      con.load_extension(name)                       -- load an installed extension
    See: https://duckdb.org/docs/stable/clients/python/reference/index
    """
    if not load_only:
        if repository == "community":
            con.install_extension(extension_name, repository="community")
        elif repository == "core":
            con.install_extension(extension_name, repository="core")
        else:
            con.install_extension(extension_name)
    con.load_extension(extension_name)


def _load_extension(
    con: duckdb.DuckDBPyConnection, extension_name: str
) -> tuple[bool, list[str], str | None]:
    """Try repositories in an order that matches DuckDB extension docs. Returns (success, errors, source name).

    Repository strategy:
    - EXTENSION_COMMUNITY_REPO_FIRST: community first, then official, then bundled
    - EXTENSION_CORE_ONLY: official only, then bundled (never community -- wrong origin)
    - Default: official first, then community, then bundled
    """
    errors: list[str] = []

    if extension_name in EXTENSION_COMMUNITY_REPO_FIRST:
        # Community-only extensions (e.g. duckdb_mcp, httpserver)
        attempts: list[tuple[str, str | None, bool]] = [
            ("community", "community", False),
            ("default", None, False),
            ("bundled", None, True),
        ]
    elif extension_name in EXTENSION_CORE_ONLY:
        # Core/official-only extensions (e.g. ducklake). Never try community --
        # that would fail with "already installed from a different origin".
        attempts = [
            ("default", None, False),
            ("bundled", None, True),
        ]
    else:
        # Default: try official first, community as fallback, then bundled
        attempts = [
            ("default", None, False),
            ("community", "community", False),
            ("bundled", None, True),
        ]

    for source, repo, load_only in attempts:
        try:
            _install_and_load_extension(
                con, extension_name, repository=repo, load_only=load_only
            )
            return True, errors, source
        except Exception as exc:
            err_msg = str(exc).strip()
            if len(err_msg) > 200:
                err_msg = err_msg[:197] + "..."
            errors.append(f"{source}: {err_msg}")

    return False, errors, None


def try_load_extension(
    con: duckdb.DuckDBPyConnection,
    extension_name: str,
    from_community: bool = False,
) -> bool:
    """Try to load a single extension (best-effort). Returns True if loaded. Used by tests."""
    if is_extension_loaded(con, extension_name):
        return True
    attempts: list[tuple[str | None, str]] = [
        (f"INSTALL {extension_name} FROM community;", f"LOAD {extension_name};")
        if from_community
        else (f"INSTALL {extension_name};", f"LOAD {extension_name};"),
        (None, f"LOAD {extension_name};"),
    ]
    for install_stmt, load_stmt in attempts:
        try:
            if install_stmt:
                con.sql(install_stmt)
            con.sql(load_stmt)
            return True
        except Exception:
            continue
    return False


def load_duckdb_extensions(
    con: duckdb.DuckDBPyConnection,
    extensions: Iterable[ExtensionSpec],
    *,
    progress: Progress | None = None,
    task_id: TaskID | None = None,
) -> tuple[list[str], list[str]]:
    """Load DuckDB extensions. Returns (loaded_names, optional_skipped_names).

    Raises RuntimeError if any required extension fails.
    When progress/task_id are set, per-extension INFO logs are omitted (use progress UI).
    """
    specs = tuple(extensions)
    loaded: list[str] = []
    skipped_optional: list[str] = []
    failed_required: list[tuple[str, str]] = []
    use_progress = progress is not None and task_id is not None
    tid = task_id

    for extension_name, required in specs:
        if is_extension_loaded(con, extension_name):
            loaded.append(extension_name)
            if use_progress and progress is not None and tid is not None:
                progress.update(tid, description=f"[dim]{extension_name}[/] (cached)")
                progress.advance(tid)
            continue

        if use_progress and progress is not None and tid is not None:
            progress.update(tid, description=f"[cyan]{extension_name}[/]")

        ok, errors, source = _load_extension(con, extension_name)
        if ok:
            loaded.append(extension_name)
            if use_progress:
                if progress is not None and tid is not None:
                    src = f" [{source}]" if source else ""
                    progress.update(tid, description=f"[green]✓[/] [cyan]{extension_name}[/]{src}")
                    progress.advance(tid)
            else:
                if source == "community":
                    log.info("Loaded extension %s from community", extension_name)
                elif source == "bundled":
                    log.info("Loaded bundled extension: %s", extension_name)
                else:
                    log.info("Loaded extension: %s", extension_name)
            continue

        detail = "; ".join(errors)
        if required:
            log.error("REQUIRED extension %s failed: %s", extension_name, detail)
            failed_required.append((extension_name, detail))
        else:
            skipped_optional.append(extension_name)
            log.warning(
                "Optional extension %s skipped: %s",
                extension_name,
                detail[:500] if detail else "(no detail)",
            )
            if use_progress and progress is not None and tid is not None:
                progress.update(tid, description=f"[yellow]⚠[/] [dim]{extension_name}[/] (skipped)")
                progress.advance(tid)

    if failed_required:
        names = ", ".join(n for n, _ in failed_required)
        msg = f"Required extension(s) failed: {names}. Check log for details."
        raise RuntimeError(msg)

    if skipped_optional:
        log.info("Optional extensions skipped: %s", ", ".join(skipped_optional))

    return loaded, skipped_optional


def wal_file_path(database_file: str) -> Path:
    """Return the WAL path for a DuckDB database file (``<file>.db`` → ``<file>.db.wal``)."""
    return Path(str(Path(database_file).resolve()) + ".wal")


def _is_wal_replay_failure(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "wal" in msg
        or "replaying" in msg
        or "replay" in msg
        or "getdefaultdatabase" in msg
    )


def _apply_checkpoint_on_shutdown(con: duckdb.DuckDBPyConnection) -> None:
    """Checkpoint on shutdown merges WAL into the DB file (DuckDB docs: configuration pragmas)."""
    try:
        con.execute("PRAGMA enable_checkpoint_on_shutdown")
    except Exception as exc:
        log.debug("PRAGMA enable_checkpoint_on_shutdown: %s", exc)


def connect_duckdb_persistent(database_path: str) -> duckdb.DuckDBPyConnection:
    """
    Open a persistent DuckDB file. If WAL replay fails, move ``*.wal`` aside once and retry.

    Uncommitted transactions in a broken WAL are lost; the main ``.db`` file is kept. See DuckDB
    crash recovery: a normal reopen replays WAL; if replay errors internally, discarding WAL is
    the last resort. After open, enables ``PRAGMA enable_checkpoint_on_shutdown`` when supported.
    """
    if database_path == ":memory:":
        return duckdb.connect(database=database_path)
    resolved = str(Path(database_path).resolve())
    try:
        con = duckdb.connect(resolved)
    except Exception as exc:
        if not _is_wal_replay_failure(exc):
            raise
        wal = wal_file_path(resolved)
        if not wal.is_file():
            raise
        aside = wal.with_name(f"{wal.name}.broken.{int(time.time())}")
        log.warning(
            "DuckDB WAL replay failed (%s); moving WAL aside to %s and reconnecting once.",
            exc,
            aside.name,
        )
        try:
            wal.rename(aside)
        except OSError as err:
            log.error("Could not move WAL file aside: %s", err)
            raise exc from err
        con = duckdb.connect(resolved)
    _apply_checkpoint_on_shutdown(con)
    return con


def build_http_auth_header(api_key: str | None) -> str:
    """Format the Query.Farm auth header value for httpserve_start()."""
    return f"X-API-Key {api_key}" if api_key else ""


def start_http_server(
    con: duckdb.DuckDBPyConnection,
    port: int,
    api_key: str | None = None,
    host: str = "0.0.0.0",
) -> None:
    """Start the DuckDB HTTP server with parameter binding."""
    if not 1 <= int(port) <= 65535:
        raise ValueError(f"Invalid HTTP port: {port}")

    con.execute(
        "SELECT httpserve_start(?, ?, ?)",
        [host, int(port), build_http_auth_header(api_key)],
    )
