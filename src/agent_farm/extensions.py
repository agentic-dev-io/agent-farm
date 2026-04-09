"""DuckDB extensions loaded at runtime (install + load). Single source of truth."""

from __future__ import annotations

ExtensionSpec = tuple[str, bool]

# (extension_name, required). Optional extensions may fail on some platforms; required aborts bootstrap.
DUCKDB_EXTENSIONS: tuple[ExtensionSpec, ...] = (
    ("json", True),
    ("minijinja", True),
    ("json_schema", True),
    ("duckdb_mcp", True),
    ("httpfs", True),
    ("http_client", True),
    ("httpserver", False),
    ("vss", False),
    ("fts", False),
    ("icu", True),
    ("ducklake", True),   # Required: shared persistent state (notes, sessions, approvals, app instances)
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
