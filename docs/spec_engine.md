# Spec Engine

The **Spec Engine** is the central "Spec-OS" for all agents in Agent Farm. It uses DuckDB with specialized extensions plus Python UDFs to manage specifications, runtime state, approvals, coordination events, embeddings, and remote MCP access from one initialized database.

## Overview

The Spec Engine provides:
- **Unified specification storage** - All specs in one place with consistent schema
- **Template rendering** - MiniJinja templates for prompts and plans
- **Schema validation** - JSON Schema validation for payloads
- **Runtime workflows** - Persist sessions, approvals, org calls, and radio events
- **RAG and knowledge storage** - Embeddings, conversation memory, and org knowledge bases
- **MCP integration** - Connect to remote MCP servers from the Python API and DuckDB runtime
- **HTTP API** - Optional REST-like interface for non-MCP clients

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Agent (e.g., Pia)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Spec Engine (DuckDB)                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  minijinja  │ │ json_schema │ │  duckdb_mcp │           │
│  │ (templates) │ │ (validate)  │ │ (MCP client)│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    spec_objects                         ││
│  │  agents | skills | apis | schemas | templates | ...     ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────┐ ┌─────────────┐                           │
│  │  httpserver │ │    macros   │                           │
│  │ (HTTP API)  │ │  (SQL ops)  │                           │
│  └─────────────┘ └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Using the MCP Server

```bash
# Start the interactive REPL
agent-farm

# Start the Agent Farm MCP server
agent-farm mcp

# Or with persistent database
DUCKDB_DATABASE=my_specs.db agent-farm mcp

# With HTTP API enabled
SPEC_ENGINE_HTTP_PORT=9999 SPEC_ENGINE_API_KEY=secret agent-farm mcp
```

When `agent-farm mcp` sees `SPEC_ENGINE_HTTP_PORT` and `SPEC_ENGINE_API_KEY`, the bootstrap path calls `httpserve_start(...)` directly. That runtime path is equivalent to the SQL helper `SELECT spec_http_start(...)`.

### From Python

```python
import duckdb
from agent_farm.spec_engine import SpecEngine

# Create connection and initialize
con = duckdb.connect(":memory:")
engine = SpecEngine(con)
engine.initialize()

# List all agents
agents = engine.spec_list(kind="agent")

# Get a specific spec
pia = engine.spec_get(kind="agent", name="pia")

# Search specs
results = engine.spec_search("planner")

# Create a new spec
engine.spec_create(
    kind="agent",
    name="nova",
    summary="Research assistant agent",
    status="draft",
    payload={"role": "researcher", "model": "claude-3"}
)
```

## Extensions

The Spec Engine uses these DuckDB extensions:

| Extension | Purpose | Required |
|-----------|---------|----------|
| `minijinja` | Render MiniJinja templates for prompts/plans | Yes |
| `json_schema` | Validate JSON payloads against schemas | Yes |
| `duckdb_mcp` | MCP client/server integration | Yes |
| `httpserver` | Expose DuckDB as HTTP OLAP API | No |
| `json` | JSON manipulation | Yes |
| `httpfs` | HTTP filesystem access | Yes |
| `http_client` | HTTP requests for SQL macros | Yes |
| `vss` | Vector similarity search | No |
| `fts` | Full-text search | No |
| `jsonata` | JSON transformation | No |
| `bitfilters` | Deduplication helpers | No |
| `lindel` | Space-filling curve helpers | No |
| `shellfs` | Shell-backed SQL tools | No |

Required extensions are loaded during bootstrap and reused by `SpecEngine` when it binds to the same connection.

Vector search is optional: the Python helpers `search_similar()` and `hybrid_search()`, plus the SQL RAG macros in `spec/rag.sql`, require the `vss` extension at runtime.

## Bootstrap And Runtime State

Agent Farm bootstraps DuckDB in this order:

1. Load DuckDB extensions.
2. Initialize the Spec Engine schema, macros, intelligence layer, and seed data.
3. Register Python UDFs used by SQL and runtime workflows.
4. Create runtime tables for sessions, approvals, radio messages, and org coordination.
5. Load top-level SQL macros.

In addition to spec tables, the initialized database contains runtime tables such as:

- `agent_sessions` for persisted REPL and agent state
- `pending_approvals` for approval requests and decisions
- `org_calls` for inter-org dispatch history
- `radio_messages` and `radio_subscriptions` for persistent coordination events

## Schema

### Core Tables

```sql
-- Main specification objects
CREATE TABLE spec_objects (
    id               INTEGER PRIMARY KEY,
    kind             VARCHAR NOT NULL,
    name             VARCHAR NOT NULL,
    version          VARCHAR NOT NULL DEFAULT '1.0.0',
    status           VARCHAR NOT NULL DEFAULT 'draft',
    summary          VARCHAR NOT NULL,
    source_type      VARCHAR DEFAULT 'internal',
    source_url       VARCHAR,
    source_ref       VARCHAR,
    upstream_version VARCHAR,
    last_sync        TIMESTAMP,
    sync_status      VARCHAR DEFAULT 'none',
    confidence       REAL DEFAULT 1.0,
    use_count        INTEGER DEFAULT 0,
    success_rate     REAL DEFAULT 0.0,
    created_at       TIMESTAMP DEFAULT current_timestamp,
    updated_at       TIMESTAMP DEFAULT current_timestamp,
    UNIQUE (kind, name, version)
);

-- Documentation for specs
CREATE TABLE spec_docs (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,
    doc         VARCHAR NOT NULL,
    doc_format  VARCHAR DEFAULT 'markdown',
    created_at  TIMESTAMP DEFAULT current_timestamp
);

-- JSON payloads for specs
CREATE TABLE spec_payloads (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,
    payload     VARCHAR,            -- JSON stored as string
    schema_ref  VARCHAR,            -- Reference to a schema spec
    created_at  TIMESTAMP DEFAULT current_timestamp
);
```

IDs for spec tables are allocated through DuckDB sequences, not via `MAX(id) + 1`, so writes are safe under concurrent usage.

### Intelligence Tables

The intelligence layer extends the core schema with:

- `spec_embeddings`, including `chunk_index` with `UNIQUE (content_hash, chunk_index)` for chunked documents
- `knowledge_studio`, including `options`, `chosen_option`, `rationale`, `user_feedback`, and `performance`
- `knowledge_ops`, including `artifact_refs`, `metrics`, and `duration_ms`
- `memory_conversations` for long-term session memory

### Spec Kinds

| Kind | Description | Example |
|------|-------------|---------|
| `agent` | Agent configurations (role, model, tools, prompts) | Pia the planner |
| `skill` | Skill definitions with tool schemas | duckdb-spec-engine |
| `api` | API specifications (OpenAI, Claude, custom) | openai-chat-completions |
| `protocol` | Protocol definitions (MCP, HTTP, GraphQL) | mcp |
| `schema` | JSON Schemas for validation | agent_config_schema |
| `task_template` | MiniJinja templates for task plans | plan_pia_swarm |
| `prompt_template` | MiniJinja templates for prompts | agent_system_prompt |
| `workflow` | Multi-step workflow definitions | agent_onboarding |
| `ui` | UI component specifications | plan_viewer |
| `open_response` | Open Response format specs | - |
| `org` | Organization configurations | DevOrg, OpsOrg |
| `tool` | Individual tool definitions | - |
| `macro` | SQL macros seeded into the Spec Engine as internal self-knowledge | `spec_http_start`, `spec_search` |

Macro specs are seeded from SQL files by `seed_macros_to_spec_engine()` with `kind='macro'`.

### Convenience Views

```sql
-- Pre-built views for common queries
SELECT * FROM spec_agents_view;          -- All agents with docs/payloads
SELECT * FROM spec_skills_view;          -- All skills
SELECT * FROM spec_apis_view;            -- All APIs
SELECT * FROM spec_schemas_view;         -- All JSON schemas
SELECT * FROM spec_task_templates_view;  -- All task templates
SELECT * FROM spec_prompt_templates_view;-- All prompt templates
SELECT * FROM spec_full_view;            -- All specs joined
```

## MCP Tools

### spec_list

List specs by kind with optional filters.

```json
// Input
{"kind": "agent", "status": "active", "limit": 50}

// Output
[
    {"id": 10, "kind": "agent", "name": "pia", "version": "1.0.0", "status": "active", "summary": "..."}
]
```

**SQL Equivalent:**
```sql
SELECT * FROM spec_list_by_kind('agent');
SELECT * FROM spec_list_active();
```

### spec_get

Get a single spec by ID or by kind+name.

```json
// Input (by ID)
{"id": 10}

// Input (by kind+name)
{"kind": "agent", "name": "pia", "version": "1.0.0"}

// Output
{
    "id": 10,
    "kind": "agent",
    "name": "pia",
    "version": "1.0.0",
    "status": "active",
    "summary": "Pia is the master planner agent...",
    "doc": "# Pia - Master Planner Agent\n...",
    "payload": {"name": "Pia", "role": "planner", ...},
    "schema_ref": "agent_config_schema"
}
```

**SQL Equivalent:**
```sql
SELECT * FROM spec_get('agent', 'pia');
SELECT * FROM spec_get_by_id(10);
```

### spec_search

Search specs by query string (searches name, summary, and docs).

```json
// Input
{"query": "planner"}

// Output
[
    {"id": 10, "kind": "agent", "name": "pia", ...}
]
```

**SQL Equivalent:**
```sql
SELECT * FROM spec_search('planner');
SELECT * FROM spec_search_full('planner');  -- Also searches doc content
```

### render_from_template

Render a MiniJinja template with context.

```json
// Input
{
    "template_name": "plan_pia_swarm",
    "context": {
        "task_name": "Deploy User Service",
        "objective": "Deploy the user management microservice",
        "steps": [
            {"name": "Build", "org": "DevOrg", "tool": "build_service", "input": {}}
        ],
        "success_criteria": ["All tests pass", "Service responds"]
    }
}

// Output
{
    "rendered": "# Execution Plan: Deploy User Service\n\n**Created by**: Pia\n..."
}
```

**SQL Equivalent:**
```sql
SELECT spec_render_template('plan_pia_swarm', '{"task_name": "Test", ...}');
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');
```

### validate_payload_against_spec

Validate a JSON payload against a spec's schema.

```json
// Input
{
    "kind": "schema",
    "name": "agent_config_schema",
    "payload": {"name": "test", "role": "planner"}
}

// Output (success)
{"ok": true, "errors": []}

// Output (failure)
{"ok": false, "errors": ["Property 'role' must be one of: ..."]}
```

**SQL Equivalent:**
```sql
SELECT spec_validate('agent_config_schema', '{"name": "test", "role": "planner"}');
SELECT spec_is_valid('agent_config_schema', '{"name": "test"}');
```

### MCP Remote Helpers

```sql
-- Call a remote MCP tool
SELECT mcp_call_remote_tool('server_name', 'tool_name', '{"arg": "value"}');

-- Get a resource from a remote MCP server
SELECT mcp_get_remote_resource('server_name', 'resource://uri');
```

The SQL names are compatibility wrappers: `mcp_call_remote_tool()` wraps DuckDB's `mcp_call_tool()`, and `mcp_get_remote_resource()` wraps `mcp_get_resource()`.

For programmatic remote MCP access, prefer the Python methods `SpecEngine.mcp_query_remote()` and `SpecEngine.mcp_call_remote_tool()`.

## HTTP API

The Spec Engine can be exposed over HTTP using the `httpserver` extension.

### Starting the Server

```bash
# Via environment variables
export SPEC_ENGINE_HTTP_PORT=9999
export SPEC_ENGINE_API_KEY=your-secret-key
agent-farm mcp
```

`agent-farm mcp` reads those environment variables and starts the Query.Farm HTTP server via `httpserve_start(...)`. The SQL macro below is the in-database equivalent.

```sql
-- Via SQL
SELECT spec_http_start(9999, 'your-secret-key');
```

### Example Requests

```bash
# List all specs
curl -X POST \
     -H "X-API-Key: your-secret-key" \
     -d "SELECT * FROM spec_list_active()" \
     http://localhost:9999/

# Get a specific spec
curl -X POST \
     -H "X-API-Key: your-secret-key" \
     -d "SELECT * FROM spec_full_view WHERE name = 'pia'" \
     http://localhost:9999/

# Search specs
curl -X POST \
     -H "X-API-Key: your-secret-key" \
     -d "SELECT * FROM spec_search('planner')" \
     http://localhost:9999/

# Get statistics
curl -X POST \
     -H "X-API-Key: your-secret-key" \
     -d "SELECT * FROM spec_stats()" \
     http://localhost:9999/
```

## Agent Usage Guide

## Runtime Workflows

### Approval Flow

Approval requests are persisted in `pending_approvals` and can be resolved from either SQL or the CLI.

```sql
SELECT request_approval(
    'session-1',
    'shell_run',
    '{"cmd":"docker deploy my-service"}',
    'Destructive operation'
);

SELECT get_pending_approvals('session-1');
SELECT resolve_approval(1, 'approved', 'operator');
```

```bash
agent-farm approval list
agent-farm approval resolve 1 approved --resolved-by operator
```

### REPL Streaming

The REPL streams model output incrementally when the active backend supports streaming. If the backend or request path does not support streaming, Agent Farm falls back to the standard buffered response path automatically.

### Persistent Radio Events

Radio/pub-sub events are stored in DuckDB tables so queued messages survive process restarts when you use a file-backed database.

```sql
SELECT radio_transmit_message('builds', '{"state":"queued"}');
SELECT radio_listen('builds', 1000);
SELECT radio_channel_list();
```

### For Pia (Planner Agent)

Pia should use the Spec Engine to:

1. **Discover capabilities**: Use `spec_list` to find available skills and tools
2. **Get agent configs**: Use `spec_get` to fetch agent configurations
3. **Create plans**: Use `render_from_template` with `plan_pia_swarm`
4. **Validate inputs**: Use `validate_payload_against_spec` before executing

**Example workflow:**

```
1. User: "Build a REST API for user management"

2. Pia: spec_list(kind="skill") -> Find available skills

3. Pia: spec_get(kind="skill", name="duckdb-spec-engine") -> Get skill details

4. Pia: render_from_template(
       template_name="plan_pia_swarm",
       context={
           "task_name": "Build User API",
           "objective": "Create a REST API for user CRUD operations",
           "steps": [
               {"name": "Design Schema", "org": "ResearchOrg", "tool": "spec_search"},
               {"name": "Implement API", "org": "DevOrg", "tool": "code_write"},
               {"name": "Write Tests", "org": "DevOrg", "tool": "test_write"},
               {"name": "Deploy", "org": "OpsOrg", "tool": "deploy_service"}
           ],
           "success_criteria": ["API responds to /users", "Tests pass", "Deployed"]
       }
   )

5. Pia: Execute plan by calling organizations
```

### For Other Agents

All agents can:

1. **Look up their own config**: `spec_get(kind="org", name="DevOrg")`
2. **Find available tools**: `spec_list(kind="tool")`
3. **Validate payloads**: Before sending to external APIs
4. **Render prompts**: Use prompt templates for consistent communication

## Seed Data

The Spec Engine comes pre-seeded with:

### Schemas
- `agent_config_schema` - Validates agent configurations
- `skill_config_schema` - Validates skill definitions
- `task_template_schema` - Validates template payloads

### Agents
- `pia` - Master planner agent for orchestrating swarm workflows

### Skills
- `duckdb-spec-engine` - Core skill for spec management (5 tools)
- `surrealdb-memory` - Persistent agent memory (3 tools)
- `n8n-orchestrator` - Workflow orchestration (3 tools)

### Templates
- `plan_pia_swarm` - MiniJinja template for execution plans
- `agent_system_prompt` - Base template for agent prompts

### Protocols/APIs
- `mcp` - Model Context Protocol specification
- `openai-chat-completions` - OpenAI API specification

### Organizations
- `DevOrg` - Development organization
- `OpsOrg` - Operations organization
- `ResearchOrg` - Research organization
- `StudioOrg` - Creative/docs organization
- `OrchestratorOrg` - Coordination organization

### Workflow
- `agent_onboarding` - Workflow for onboarding new agents

## File Structure

```
src/agent_farm/
├── main.py                  # Bootstrap, extension loading, runtime tables
├── spec_engine.py           # Python SpecEngine class and MCP-facing helpers
├── repl.py                  # Interactive REPL with streaming chat
├── udfs.py                  # Python UDFs for chat, approvals, and radio
├── sql/
│   ├── base.sql
│   ├── ollama.sql
│   ├── harness.sql
│   ├── ui.sql
│   ├── org_tools.sql
│   └── spec/
│       ├── schema.sql       # Spec schema and views
│       ├── intelligence.sql # Embeddings, memory, knowledge bases
│       ├── macros.sql       # Spec query/render/validation macros
│       ├── rag.sql          # Hybrid retrieval and memory macros
│       └── seed.sql         # Seed specs and templates
└── ...

docs/
└── spec_engine.md           # This documentation
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Path to DuckDB database | `:memory:` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | None (disabled) |
| `SPEC_ENGINE_API_KEY` | HTTP API authentication key | None |
| `OLLAMA_BASE_URL` | Ollama chat endpoint | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Anthropic API key | None |
| `ANTHROPIC_BASE_URL` | Anthropic endpoint override | `https://api.anthropic.com` |
| `SEARXNG_BASE_URL` | SearXNG endpoint for research macros | `http://searxng:8080` |

`DUCKDB_DATABASE` is the single environment variable that selects the actual database file used by Agent Farm and `SpecEngine`.

## Python API Reference

### SpecEngine Class

```python
from agent_farm.spec_engine import SpecEngine, get_spec_engine

# Get or create the engine for a specific DuckDB connection
engine = get_spec_engine(con)

# Or create a dedicated instance directly
engine = SpecEngine(con)
engine.initialize()

# List specs
specs = engine.spec_list(kind="agent", status="active", limit=10)

# Get single spec
spec = engine.spec_get(id=10)
spec = engine.spec_get(kind="agent", name="pia")

# Search specs
results = engine.spec_search("planner", limit=20)

# Render template
result = engine.render_from_template("plan_pia_swarm", {"task_name": "Test"})

# Validate payload
result = engine.validate_payload_against_spec("schema", "agent_config_schema", payload)

# CRUD operations
engine.spec_create(kind="agent", name="nova", summary="Research agent")
engine.spec_update(id=10, version="1.0.1", status="active", schema_ref="agent_config_schema")
engine.spec_delete(id=10)

# Utilities
stats = engine.get_stats()
extensions = engine.get_loaded_extensions()
kinds = engine.get_spec_kinds()

# HTTP server
engine.start_http_server(port=9999, api_key="secret")
engine.stop_http_server()

# MCP remote
engine.mcp_query_remote("server", "resource://uri")
engine.mcp_call_remote_tool("server", "tool", {"arg": "value"})

# Embeddings / org knowledge
engine.store_embedding("chunk text", [0.1, 0.2], "doc", chunk_index=0)
engine.store_org_knowledge(
    "studio",
    "Landing page direction A won",
    options=[{"name": "A"}, {"name": "B"}],
    chosen_option="A",
    rationale="Higher clarity",
    user_feedback={"approved": True},
)
engine.store_org_knowledge(
    "ops",
    "Deploy succeeded",
    artifact_refs=["artifacts/build.log"],
    metrics={"latency_ms": 82},
)
```

`get_spec_engine()` caches one `SpecEngine` per DuckDB connection. If multiple connections are active, pass `con` explicitly.

## SQL Macro Reference

### Query Macros

```sql
-- List by kind
SELECT * FROM spec_list_by_kind('agent');

-- List active specs
SELECT * FROM spec_list_active();

-- Search
SELECT * FROM spec_search('query');
SELECT * FROM spec_search_full('query');  -- includes docs

-- Get single spec
SELECT * FROM spec_get('agent', 'pia');
SELECT * FROM spec_get_v('agent', 'pia', '1.0.0');
SELECT * FROM spec_get_by_id(10);

-- Get parts
SELECT spec_get_payload('agent', 'pia');
SELECT spec_get_doc('agent', 'pia');
SELECT spec_get_template('plan_pia_swarm');

-- Statistics
SELECT * FROM spec_stats();
SELECT * FROM spec_kinds();
SELECT * FROM spec_recent(10);
```

### Template Macros

```sql
-- Render stored template
SELECT spec_render_template('template_name', '{"var": "value"}');
SELECT spec_render_template_v('template_name', '1.0.0', '{"var": "value"}');

-- Render inline template
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');
```

### Validation Macros

```sql
-- Validate against schema
SELECT spec_validate('schema_name', '{"data": "value"}');
SELECT spec_validate_against('agent', 'pia', '{"role": "planner"}');
SELECT spec_is_valid('schema_name', '{"data": "value"}');
```

### Agent Helper Macros

```sql
-- Get agent info
SELECT spec_agent_prompt('pia');
SELECT spec_agent_model('pia');
SELECT spec_skill_tools('duckdb-spec-engine');
SELECT spec_workflow_steps('agent_onboarding');
```

### MCP Macros

```sql
-- Remote MCP operations
SELECT mcp_call_remote_tool('server', 'tool', '{"arg": "value"}');
SELECT mcp_get_remote_resource('server', 'uri');
SELECT mcp_get_remote_prompt('server', 'prompt', '{"arg": "value"}');
```

These macros wrap the lower-level `mcp_call_tool()`, `mcp_get_resource()`, and `mcp_get_prompt()` functions from `duckdb_mcp`.

### HTTP Server Macros

```sql
SELECT spec_http_start(9999, 'api-key');
SELECT spec_http_stop();
```

`spec_http_start()` expands to `httpserve_start('0.0.0.0', port, COALESCE('X-API-Key ' || api_key, ''))` and matches the behavior used by the CLI/bootstrap path.
