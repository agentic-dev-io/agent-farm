"""
MCP surface -- stub retained for import compatibility.

duckdb_mcp server-side registration functions (mcp_register_prompt_template,
mcp_publish_query) are MCP CLIENT calls, not server-side surface registration.
They register prompts/resources WITH other MCP servers, not FOR serving them.

The MCP transport is now FastMCP (mcp Python SDK) -- see mcp_host.py.
Prompts, resources, and tools can be added to the FastMCP server there directly.
duckdb_mcp is still loaded by bootstrap_db as an MCP CLIENT (to call external servers).
"""
from __future__ import annotations

import logging

import duckdb

log = logging.getLogger("agent_farm.mcp_surface")


def register_mcp_surface(con: duckdb.DuckDBPyConnection) -> None:
    """No-op: MCP surface registration is handled in mcp_host.py (FastMCP)."""
    log.debug("register_mcp_surface: no-op (FastMCP transport in mcp_host.py)")
