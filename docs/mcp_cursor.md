# Agent Farm MCP + Cursor (facts)

References: [Cursor MCP](https://cursor.com/docs/context/mcp), [duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp.html), [MCP](https://modelcontextprotocol.io/introduction).

## What must happen before stdio works

`duckdb_mcp` starts the MCP protocol only when `mcp_server_start('stdio', …)` runs. That call **blocks** (stdio server loop). Everything Agent Farm needs in DuckDB must be loaded **before** that line: extensions, Spec Engine, SQL macros, etc.

So the editor’s MCP client waits for the process to **finish bootstrap** and then reach `mcp_server_start`. If that takes longer than the host’s wait, you see **Client closed** / **Server not yet created** — not a random bug.

## DuckDB file lock

A single `.db` file can only be opened for writing by **one** process at a time. If the REPL (or tests) already has `~/.agent_farm/agent_farm.db`, a second process cannot open the same path.

**Default for `agent-farm mcp`:** `~/.agent_farm/agent_farm_mcp.db` (separate from the REPL default `agent_farm.db`). Override with `DUCKDB_DATABASE` or `--db` if you intentionally want one shared file — then close the other session first.

## Cursor debugging

- Output panel → **MCP** / **MCP Logs** (see [Cursor MCP FAQ](https://cursor.com/docs/context/mcp)).
- Toggle the server off/on under **Settings → Features → Model Context Protocol** if a stuck process is suspected.

There is **no** `mcp.json` field documented by Cursor for stdio startup timeout; behavior depends on the Cursor version. If init stays slow, warm the machine once (`agent-farm status`) so DuckDB extensions are already installed under the user cache.
