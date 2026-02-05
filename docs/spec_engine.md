# Spec Engine

The **Spec Engine** is the central "Spec-OS" for all agents in Agent Farm. It uses DuckDB with specialized extensions to manage ALL specifications including agents, skills, workflows, APIs, JSON schemas, templates, and more.

## Overview

The Spec Engine provides:
- **Unified specification storage** - All specs in one place with consistent schema
- **Template rendering** - MiniJinja templates for prompts and plans
- **Schema validation** - JSON Schema validation for payloads
- **MCP integration** - Connect to remote MCP servers from SQL
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
# Start the Agent Farm MCP server
agent-farm

# Or with persistent database
DUCKDB_DATABASE=my_specs.db agent-farm

# With HTTP API enabled
SPEC_ENGINE_HTTP_PORT=9999 SPEC_ENGINE_API_KEY=secret agent-farm
```

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
| `httpfs` | HTTP filesystem access | No |
| `http_client` | HTTP requests | No |

## Schema

### Core Tables

```sql
-- Main specification objects
CREATE TABLE spec_objects (
    id          INTEGER PRIMARY KEY,
    kind        VARCHAR NOT NULL,   -- 'agent', 'skill', 'api', 'schema', ...
    name        VARCHAR NOT NULL,
    version     VARCHAR NOT NULL DEFAULT '1.0.0',
    status      VARCHAR NOT NULL DEFAULT 'draft',
    summary     VARCHAR NOT NULL,
    created_at  TIMESTAMP,
    updated_at  TIMESTAMP,
    UNIQUE (kind, name, version)
);

-- Documentation for specs
CREATE TABLE spec_docs (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,
    doc         VARCHAR NOT NULL,
    doc_format  VARCHAR DEFAULT 'markdown'
);

-- JSON payloads for specs
CREATE TABLE spec_payloads (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,
    payload     VARCHAR,            -- JSON stored as string
    schema_ref  VARCHAR             -- Reference to a schema spec
);
```

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
-- List resources from a remote MCP server
SELECT * FROM mcp_list_remote('server_name');

-- List tools from a remote MCP server
SELECT * FROM mcp_list_tools_remote('server_name');

-- Call a remote MCP tool
SELECT mcp_call_remote_tool('server_name', 'tool_name', '{"arg": "value"}');

-- Get a resource from a remote MCP server
SELECT mcp_get_remote_resource('server_name', 'resource://uri');
```

## HTTP API

The Spec Engine can be exposed over HTTP using the `httpserver` extension.

### Starting the Server

```bash
# Via environment variables
export SPEC_ENGINE_HTTP_PORT=9999
export SPEC_ENGINE_API_KEY=your-secret-key
agent-farm
```

```sql
-- Via SQL
SELECT spec_http_start(9999, 'your-secret-key');
```

### Example Requests

```bash
# List all specs
curl -X POST \
     -H "X-API-Key: your-secret-key" \
     -d "SELECT * FROM api_specs_list" \
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
     -d "SELECT * FROM api_stats" \
     http://localhost:9999/
```

## Agent Usage Guide

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
db/
├── spec_engine_init.sql     # Extension installation
├── spec_engine_schema.sql   # Table definitions
├── spec_engine_macros.sql   # SQL macros (30+)
├── spec_engine_seed.sql     # Initial data (20+ specs)
└── spec_engine_http.sql     # HTTP API configuration

src/agent_farm/
├── spec_engine.py           # Python SpecEngine class
├── main.py                  # Entry point (integrates Spec Engine)
└── ...

docs/
└── spec_engine.md           # This documentation
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Path to DuckDB database | `:memory:` |
| `SPEC_ENGINE_DB` | Path to Spec Engine database | `db/spec_engine.db` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | None (disabled) |
| `SPEC_ENGINE_API_KEY` | HTTP API authentication key | None |

## Python API Reference

### SpecEngine Class

```python
from agent_farm.spec_engine import SpecEngine, get_spec_engine

# Get singleton instance
engine = get_spec_engine(con)

# Or create new instance
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
engine.spec_update(id=10, status="active")
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
```

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
SELECT * FROM mcp_list_remote('server');
SELECT * FROM mcp_list_tools_remote('server');
SELECT * FROM mcp_list_prompts_remote('server');
SELECT mcp_call_remote_tool('server', 'tool', '{"arg": "value"}');
SELECT mcp_get_remote_resource('server', 'uri');
SELECT mcp_get_remote_prompt('server', 'prompt', '{"arg": "value"}');
```

### HTTP Server Macros

```sql
SELECT spec_http_start(9999, 'api-key');
SELECT spec_http_stop();
```
