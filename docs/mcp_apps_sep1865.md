# MCP Apps (SEP-1865) — Agent Farm alignment

This document maps [SEP-1865: MCP Apps](https://spec.modelcontextprotocol.io/) (Stable 2026-01-26, extension `io.modelcontextprotocol/ui`) to Agent Farm’s implementation and security posture.

## What we implement in data

| SEP concept | Agent Farm |
|-------------|------------|
| `ui://…` resource URI | `mcp_apps.resource_uri` (e.g. `ui://agent-farm/app/app.studio.chart`) |
| MIME type `text/html;profile=mcp-app` | `mcp_apps.mime_type` (default) |
| `UIResource._meta` (CSP, permissions, border) | `mcp_apps.ui_meta` JSON — shape matches `_meta` for `resources/read` (nested `ui.csp`, `ui.prefersBorder`, …) |
| Resource listing | View `mcp_ui_resources_declaration` (`uri`, `name`, `description`, `mimeType`, `_meta`) |

Templates in `mcp_app_templates` use Tailwind via `https://cdn.tailwindcss.com`. **Declared** in `ui_meta` as:

```json
{
  "ui": {
    "csp": {
      "resourceDomains": ["https://cdn.tailwindcss.com"],
      "connectDomains": []
    },
    "prefersBorder": true
  }
}
```

Hosts MUST NOT add origins beyond those declared (SEP: *No Loosening*).

## Tool ↔ UI linkage (SEP)

Tools SHOULD expose:

```json
"_meta": {
  "ui": {
    "resourceUri": "ui://agent-farm/app/<app_id>",
    "visibility": ["model", "app"]
  }
}
```

- Prefer nested `_meta.ui.resourceUri` (flat `_meta["ui/resourceUri"]` is deprecated).
- `visibility` defaults to `["model", "app"]` per SEP if omitted.

**Runtime wiring:** The DuckDB community extension `duckdb_mcp` exposes the MCP server (`mcp_server_start`). Published tools/resources depend on the installed `duckdb_mcp` version (e.g. `mcp_publish_table` / `mcp_publish_query`). Full automatic registration of SEP-shaped tools with `_meta.ui` may require a `duckdb_mcp` build that accepts tool metadata JSON — until then, hosts MAY consume `mcp_ui_resources_declaration` and bind tools in a proxy layer.

## Capability negotiation

Clients advertise MCP Apps with:

```json
"capabilities": {
  "extensions": {
    "io.modelcontextprotocol/ui": {
      "mimeTypes": ["text/html;profile=mcp-app"]
    }
  }
}
```

Servers SHOULD register UI-linked tools only after detecting this extension (SEP *Graceful Degradation* — text-only tools otherwise).

Agent Farm does not yet inject this into `mcp_server_start(..., '{}')` JSON automatically; extend the last argument when your host supports MCP Apps.

## `resources/read` content

SEP requires:

- `mimeType`: `text/html;profile=mcp-app`
- `text` or `blob` with valid HTML5
- Optional `contents[]._meta.ui` for CSP (same shape as declaration)

Rendered HTML is produced by the app pipeline (`render_app` / Python MiniJinja). The **declaration** row in `mcp_apps` describes policy; the **body** is returned when the host loads the template and applies tool results.

## Security checklist (hosts + operators)

1. **Sandbox** — Host renders Views in sandboxed iframes; communication via MCP JSON-RPC / postMessage (SEP).
2. **CSP** — Enforce declared `connectDomains` / `resourceDomains`; default restrictive policy if metadata omitted (SEP Host Behavior).
3. **Audit** — Log CSP and tool–UI bindings (SEP *Audit Trail*).
4. **No undeclared network** — Templates must not add scripts from domains not listed in `ui_meta` (update `ui_meta` if you change templates).

## Schema migration

Existing databases get new columns via `ensure_mcp_apps_sep_schema()` during bootstrap (`main.py`): `resource_uri`, `mime_type`, `ui_meta`, then backfill.

## References

- SEP-1865 (MCP Apps) — extension `io.modelcontextprotocol/ui`, `ui://` scheme, `text/html;profile=mcp-app`.
- DuckDB `duckdb_mcp` — [community extension docs](https://duckdb.org/community_extensions/extensions/duckdb_mcp.html).
