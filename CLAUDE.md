# Claude Code Instructions

This file provides context and instructions for AI agents (Claude, Copilot, etc.) working with the Agent Farm codebase.

## Project Overview

**Agent Farm** is a DuckDB-powered MCP server with a central **Spec Engine** that manages specifications for LLM agents. It provides:

- Unified specification storage (agents, skills, templates, schemas)
- Template rendering via MiniJinja
- JSON Schema validation
- MCP protocol integration
- SQL macros for LLM operations, web search, shell execution

## Architecture

```
agent-farm/
├── src/agent_farm/          # Main Python package
│   ├── main.py              # Entry point, MCP server initialization
│   ├── spec_engine.py       # Spec Engine class (central component)
│   ├── orgs.py              # Organization configurations
│   ├── udfs.py              # Python UDFs for DuckDB
│   ├── schemas.py           # Data models and enums
│   └── sql/                 # Modular SQL files (01-09)
├── db/                      # Spec Engine SQL files
│   ├── spec_engine_schema.sql
│   ├── spec_engine_macros.sql
│   ├── spec_engine_seed.sql
│   └── spec_engine_http.sql
├── tests/                   # Test suite
├── docs/                    # Documentation
└── .github/                 # CI/CD, agents, instructions
```

## Key Components

### 1. Spec Engine (`src/agent_farm/spec_engine.py`)

The central specification management system. Key methods:

```python
# Query operations
spec_list(kind, status, limit)      # List specs by kind
spec_get(id, kind, name, version)   # Get single spec
spec_search(query, limit)            # Search specs

# Template rendering
render_from_template(template_name, context)

# Validation
validate_payload_against_spec(kind, name, payload)

# CRUD operations
spec_create(kind, name, summary, ...)
spec_update(id, status, summary, doc, payload)
spec_delete(id)

# Utilities
get_stats()
get_loaded_extensions()
get_spec_kinds()
```

### 2. SQL Macros (`db/spec_engine_macros.sql`)

30+ SQL macros for spec operations:

```sql
-- Query macros
spec_list_by_kind('agent')
spec_search('query')
spec_get('agent', 'pia')

-- Template macros
spec_render_template('template_name', '{"context": "json"}')
spec_render('Hello {{ name }}!', '{"name": "value"}')

-- Validation macros
spec_validate('schema_name', '{"payload": "json"}')
spec_is_valid('schema_name', '{"payload": "json"}')

-- MCP remote macros
mcp_list_remote('server')
mcp_call_remote_tool('server', 'tool', '{"args": "json"}')
```

### 3. Organizations (`src/agent_farm/orgs.py`)

5 specialized organizations:
- **DevOrg** - Development and testing
- **OpsOrg** - Deployment and infrastructure
- **ResearchOrg** - Information gathering
- **StudioOrg** - Creative and documentation
- **OrchestratorOrg** - Coordination

### 4. DuckDB Extensions

Required extensions:
- `minijinja` - Template rendering
- `json_schema` - Schema validation
- `duckdb_mcp` - MCP protocol
- `json` - JSON support

Optional extensions:
- `httpserver` - HTTP API
- `httpfs`, `http_client` - HTTP operations
- `jsonata`, `vss`, `shellfs` - Advanced features

## Development Guidelines

### Code Style

- Python 3.11+ with type hints
- 100 character line limit
- Use ruff for linting
- Follow existing patterns in codebase

### SQL Macros

- Use `CREATE OR REPLACE MACRO` for all macros
- Include clear comments
- Use parameterized queries to prevent injection
- Handle NULL cases appropriately

### Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test
uv run pytest tests/test_spec_engine.py -v

# Run with coverage
uv run pytest tests/ --cov=src/agent_farm
```

### Adding New Features

1. **New Spec Kind**: Add to seed data in `db/spec_engine_seed.sql`
2. **New SQL Macro**: Add to `db/spec_engine_macros.sql`
3. **New Python Method**: Add to `src/agent_farm/spec_engine.py`
4. **New Tool**: Register in `register_spec_engine_tools()`

## Common Tasks

### Adding a New Agent Spec

```python
engine.spec_create(
    kind="agent",
    name="my-agent",
    summary="Description of the agent",
    status="draft",
    payload={
        "role": "specialist",
        "model": "claude-3",
        "tools": ["tool1", "tool2"],
        "system_prompt": "You are..."
    },
    doc="# My Agent\n\nDocumentation here...",
    schema_ref="agent_config_schema"
)
```

### Adding a New Template

```sql
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (nextval('spec_objects_seq'), 'task_template', 'my-template', '1.0.0', 'active', 'Description');

INSERT INTO spec_payloads (id, object_id, payload)
VALUES (nextval('spec_payloads_seq'), currval('spec_objects_seq'), '{
    "template": "Hello {{ name }}!\n{% for item in items %}- {{ item }}{% endfor %}",
    "variables": [
        {"name": "name", "type": "string", "required": true},
        {"name": "items", "type": "array", "required": false}
    ]
}');
```

### Querying Specs

```sql
-- Find all active agents
SELECT * FROM spec_agents_view WHERE status = 'active';

-- Search for templates related to planning
SELECT * FROM spec_search('plan');

-- Get full spec with payload
SELECT * FROM spec_get('skill', 'duckdb-spec-engine');
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Database path | `:memory:` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | None |
| `SPEC_ENGINE_API_KEY` | HTTP API key | None |

## File Conventions

- SQL files: Use `--` comments, semicolon-separated statements
- Python files: Type hints, docstrings for public methods
- Tests: Use pytest fixtures, one test class per feature

## Important Notes

1. **Spec Engine is the core** - All specifications go through the Spec Engine
2. **Extensions may fail** - Handle extension loading errors gracefully
3. **JSON stored as VARCHAR** - For DuckDB compatibility
4. **MiniJinja syntax** - Templates use Jinja2-like syntax via MiniJinja
5. **Schema validation** - Use `json_schema` extension for validation

## Quick Reference

### Start MCP Server
```bash
agent-farm
```

### Run with HTTP API
```bash
SPEC_ENGINE_HTTP_PORT=9999 agent-farm
```

### Query via HTTP
```bash
curl -X POST -H "X-API-Key: key" \
     -d "SELECT * FROM spec_list_by_kind('agent')" \
     http://localhost:9999/
```

### Python API
```python
from agent_farm.spec_engine import get_spec_engine
import duckdb

con = duckdb.connect(":memory:")
engine = get_spec_engine(con)

# Use engine methods...
```

## Links

- [Spec Engine Documentation](docs/spec_engine.md)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [MiniJinja Documentation](https://docs.rs/minijinja/latest/minijinja/)
- [JSON Schema](https://json-schema.org/)
- [MCP Protocol](https://modelcontextprotocol.io/)
