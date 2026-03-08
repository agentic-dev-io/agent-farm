"""Shared DuckDB helpers for Agent Farm runtime setup."""

from __future__ import annotations

import sys
from typing import Iterable

import duckdb

ExtensionSpec = tuple[str, bool]

SPEC_ENGINE_EXTENSION_SPECS: tuple[ExtensionSpec, ...] = (
    ("json", True),
    ("minijinja", True),
    ("json_schema", True),
    ("duckdb_mcp", True),
    ("httpfs", True),
    ("http_client", True),
    ("httpserver", False),
    ("vss", False),
    ("fts", False),
)

AGENT_FARM_EXTRA_EXTENSION_SPECS: tuple[ExtensionSpec, ...] = (
    ("icu", True),
    ("ducklake", False),
    ("jsonata", False),
    ("duckpgq", False),
    ("bitfilters", False),
    ("lindel", False),
    ("htmlstringify", False),
    ("lsh", False),
    ("shellfs", False),
    ("zipfs", False),
    ("radio", False),
)

AGENT_FARM_EXTENSION_SPECS: tuple[ExtensionSpec, ...] = (
    SPEC_ENGINE_EXTENSION_SPECS + AGENT_FARM_EXTRA_EXTENSION_SPECS
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


def _load_extension(
    con: duckdb.DuckDBPyConnection, extension_name: str
) -> tuple[bool, list[str], str | None]:
    errors: list[str] = []
    attempts = [
        ("default", f"INSTALL {extension_name};", f"LOAD {extension_name};"),
        ("community", f"INSTALL {extension_name} FROM community;", f"LOAD {extension_name};"),
        ("bundled", None, f"LOAD {extension_name};"),
    ]

    for source, install_stmt, load_stmt in attempts:
        try:
            if install_stmt:
                con.sql(install_stmt)
            con.sql(load_stmt)
            return True, errors, source
        except Exception as exc:
            errors.append(f"{source}: {exc}")

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
) -> list[str]:
    """Load the requested DuckDB extensions, logging failures to stderr."""
    loaded: list[str] = []

    for extension_name, required in extensions:
        if is_extension_loaded(con, extension_name):
            loaded.append(extension_name)
            continue

        ok, errors, source = _load_extension(con, extension_name)
        if ok:
            loaded.append(extension_name)
            if source == "community":
                print(f"Loaded extension {extension_name} from community", file=sys.stderr)
            elif source == "bundled":
                print(f"Loaded bundled extension: {extension_name}", file=sys.stderr)
            else:
                print(f"Loaded extension: {extension_name}", file=sys.stderr)
            continue

        detail = "; ".join(errors)
        if required:
            print(f"REQUIRED extension {extension_name} failed: {detail}", file=sys.stderr)
        else:
            print(f"Skipping optional extension {extension_name}: {detail}", file=sys.stderr)

    return loaded


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
