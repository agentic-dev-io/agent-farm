<div align="center">
  <img src="https://raw.githubusercontent.com/agentic-dev-io/agent-farm/master/assets/farm.jpg" alt="Agent Farm" width="100%" />
</div>

# Agent Farm

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1+-yellow.svg)](https://duckdb.org)
[![MCP](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/agentic-dev-io/agent-farm)

[![CI](https://github.com/agentic-dev-io/agent-farm/workflows/CI/badge.svg)](https://github.com/agentic-dev-io/agent-farm/actions/workflows/ci.yml)

**DuckDB Spec-OS for multi-org AI agent swarms.** Central specification management, 280+ SQL macros, interactive agent REPL, MCP Apps, meta-learning, and smart extensions.

---

## Quick Start

```bash
# Install
uv add agent-farm

# Interactive REPL (default: OrchestratorOrg)
agent-farm

# Start MCP server
agent-farm mcp

# System status
agent-farm status
```

### From Source

```bash
git clone https://github.com/agentic-dev-io/agent-farm.git
cd agent-farm
uv sync
agent-farm status
```

### Docker

```bash
docker compose up agent-farm     # MCP server + HTTP API on :8080
docker compose run test          # Run test suite
```

---

## CLI

```
agent-farm                              # Interactive REPL (Orchestrator)
agent-farm --org dev                    # REPL with DevOrg
agent-farm --session my-session         # Resume persistent session

agent-farm mcp                          # Start MCP server (stdio)
agent-farm mcp --http-port 8080         # With HTTP API

agent-farm status                       # Specs + Extensions + Orgs overview

agent-farm spec list [--kind agent]     # List specs
agent-farm spec get --id 10             # Get spec as JSON
agent-farm spec search <query>          # Full-text search

agent-farm app list                     # List MCP Apps (11+)
agent-farm app render <id>              # Render a MiniJinja app template

agent-farm sql <file.sql>               # Execute SQL against initialized DB
```

### Interactive REPL

The default mode — chat with AI agents, run slash-commands:

```
[OrchestratorOrg]> Analyze the project structure and suggest improvements
[OrchestratorOrg]> /org dev                    # Switch to DevOrg
[DevOrg]> /spec list --kind agent              # List agent specs
[DevOrg]> /sql SELECT count(*) FROM spec_objects
[DevOrg]> /status                              # Quick status summary
[DevOrg]> /exit                                # Quit (saves session if --session)
```

---

## Architecture

```
src/agent_farm/
├── cli.py             # Typer CLI (mcp, status, spec, app, sql)
├── repl.py            # Interactive REPL with slash-commands
├── main.py            # DuckDB init, extension loading, SQL macros
├── spec_engine.py     # Spec Engine (central specification management)
├── orgs.py            # 5 organizations with models, tools, security
├── schemas.py         # Data models, enums, table definitions
├── udfs.py            # Python UDFs (agent_chat, agent_tools, etc.)
└── sql/               # 280+ SQL macros
    ├── base.sql       # Utilities (url_encode, timestamps)
    ├── ollama.sql     # LLM calls (Ollama, Anthropic, cloud wrappers)
    ├── tools.sql      # Web search, shell, Python, fetch, file, git
    ├── agent.sql      # Security policies, audit, injection detection
    ├── harness.sql    # Agent harness (model routing, tool execution)
    ├── orgs.sql       # Org permissions, orchestrator routing
    ├── org_tools.sql  # SearXNG, CI/CD, notes, render jobs
    ├── ui.sql         # MCP Apps (24 MiniJinja UI templates)
    └── extensions.sql # JSONata, DuckPGQ, Radio, Bitfilters (hybrid), Lindel (hybrid)

db/                    # Spec Engine schema, macros, seed data, intelligence
tests/                 # pytest test suite
docs/                  # Documentation
```

---

## Multi-Org Swarm

5 specialized organizations with security policies, tool permissions, and denial rules:

| Org | Model | Security | Role |
|-----|-------|----------|------|
| **OrchestratorOrg** | kimi-k2.5:cloud | conservative | Task routing, coordination |
| **DevOrg** | glm-5:cloud | standard | Code, reviews, tests |
| **OpsOrg** | kimi-k2.5:cloud | power | CI/CD, deploy, render |
| **ResearchOrg** | gpt-oss:20b-cloud | conservative | SearXNG search, analysis |
| **StudioOrg** | kimi-k2.5:cloud | standard | Specs, docs, DCC briefings |

Each org has dedicated workspaces, allowed/denied tool lists, approval requirements, and smart extension integrations.

---

## SQL Macros (280+)

```sql
-- LLM calls (routed through Ollama)
SELECT deepseek('Explain quantum computing');
SELECT kimi_think('Solve step by step: ...');
SELECT qwen3_coder('Write a Python function for...');

-- Spec Engine
SELECT * FROM spec_list_by_kind('agent');
SELECT * FROM spec_search('planner');
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');

-- Web search
SELECT brave_search('DuckDB tutorial');
SELECT searxng('quantum computing');

-- Agent harness
SELECT quick_agent('agent-1', 'Summarize the project');
SELECT secure_read('agent-1', '/projects/dev/main.py');

-- Shell & Python
SELECT shell('ls -la');
SELECT py('print(2+2)');
```

See [docs/spec_engine.md](docs/spec_engine.md) for the full SQL macro reference.

---

## MCP Client Configuration

```json
{
  "mcpServers": {
    "agent-farm": {
      "command": "agent-farm",
      "args": ["mcp"],
      "env": {
        "DUCKDB_DATABASE": ".agent_memory.db"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Database path | `:memory:` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | — |
| `SPEC_ENGINE_API_KEY` | HTTP API key | — |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `BRAVE_API_KEY` | Brave Search key | — |

---

## Development

```bash
uv sync --extra dev

# Tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Coverage
uv run pytest tests/ --cov=src/agent_farm
```

---

## Documentation

- [Spec Engine Reference](docs/spec_engine.md)

---

## License

MIT — see [LICENSE](LICENSE) for details.
