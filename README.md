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

# Interactive REPL (default: AgentFarmer)
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
agent-farm                              # Interactive REPL (AgentFarmer)
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

agent-farm approval list                # List pending approvals
agent-farm approval resolve 1 approved  # Resolve approval request

agent-farm sql <file.sql>               # Execute SQL against initialized DB
```

**MCP Apps (SEP-1865):** `ui://` resources, CSP metadata, and host expectations — [docs/mcp_apps_sep1865.md](docs/mcp_apps_sep1865.md).

### Interactive REPL

The default mode — chat with AI agents, run slash-commands:

```
[AgentFarmer]> Analyze the project structure and suggest improvements
[AgentFarmer]> /org dev                    # Switch to DevOrg
[DevOrg]> /spec list --kind agent              # List agent specs
[DevOrg]> /sql SELECT count(*) FROM spec_objects
[DevOrg]> /status                              # Quick status summary
[DevOrg]> /exit                                # Quit (saves session if --session)
```

REPL responses stream incrementally when the backend supports it.

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
| **AgentFarmer** | kimi-k2.5:cloud | conservative | Task routing, coordination |
| **DevOrg** | glm-5:cloud | standard | Code, reviews, tests |
| **OpsOrg** | kimi-k2.5:cloud | power | CI/CD, deploy, render |
| **ResearchOrg** | gpt-oss:20b-cloud | conservative | SearXNG search, analysis |
| **StudioOrg** | kimi-k2.5:cloud | standard | Specs, docs, DCC briefings |

Each org has dedicated workspaces, allowed/denied tool lists, approval requirements, and smart extension integrations.

Approval requests are persisted in DuckDB and can be reviewed via `agent-farm approval list`.

Radio messages are persisted in DuckDB, so queued events survive process restarts when using a file-backed database.

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

See [docs/macros.md](docs/macros.md) for the full SQL macro reference (all 280 macros with signatures and descriptions).  
See [docs/spec_engine.md](docs/spec_engine.md) for the Spec Engine architecture and runtime guide.

---

## MCP client configuration

Copy [`mcp.json.example`](mcp.json.example) into your editor config (e.g. Cursor user `mcp.json`), replace `<PATH_TO_YOUR_AGENT_FARM_CLONE>` with your clone path. **Do not commit** a project-local `mcp.json` (gitignored).

Use `uv run --directory <clone> agent-farm mcp` (see example) so the package resolves even when the editor does not set `cwd`. Add **other** MCP servers (filesystem, search, …) in the same `mcpServers` object as needed.

**Default DB for MCP:** `~/.agent_farm/agent_farm_mcp.db` — not the same file as the REPL default (`agent_farm.db`), so the editor and a local REPL do not fight for one DuckDB lock. To use the same file as the REPL, set `env.DUCKDB_DATABASE` to that path and ensure only one process opens it.

At runtime, Agent Farm reads those configs to fill the SQL table `mcp_servers` with **other** servers only — entries that run `agent-farm mcp` are **not** listed (avoids registering yourself). Override: `AGENT_FARM_MCP_INVENTORY_INCLUDE_SELF=1` for debugging.

**Cursor / timeouts / locks:** see [docs/mcp_cursor.md](docs/mcp_cursor.md).

Optional variants (same file, extra keys): `:memory:` via `env.DUCKDB_DATABASE`; HTTP: `agent-farm mcp --http-port 9999` + `SPEC_ENGINE_API_KEY` if you expose the API.

Optional: `uv add anthropic` or `pip install agent-farm[anthropic]` if you use Claude models via the Anthropic API in UDFs.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Database path | REPL/default CLI: `~/.agent_farm/agent_farm.db`; **`agent-farm mcp`** without this env: `~/.agent_farm/agent_farm_mcp.db` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | — |
| `SPEC_ENGINE_API_KEY` | HTTP API key | — |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `ANTHROPIC_BASE_URL` | Anthropic endpoint override | `https://api.anthropic.com` |
| `SEARXNG_BASE_URL` | SearXNG endpoint | `http://searxng:8080` |
| `BRAVE_API_KEY` | Brave Search key | — |
| `AGENT_FARM_LOG` | Log file path | — |
| `AGENT_FARM_PLAIN_LOG` | Set to `1` to disable Rich progress / emoji on startup (classic logs) | — |
| `AGENT_FARM_MCP_INVENTORY_INCLUDE_SELF` | Set to `1` to include Agent Farm’s own MCP entry in `mcp_servers` (not recommended) | — |

If DuckDB fails to **replay the WAL** on open, stop other processes using the same file, then retry. The runtime moves `agent_farm.db.wal` aside to `agent_farm.db.wal.broken.<timestamp>` once and reconnects (see [DuckDB crash recovery](https://duckdb.org/docs/stable/guides/troubleshooting/crashes)); uncommitted data in that WAL is lost. `PRAGMA enable_checkpoint_on_shutdown` is applied on connect to reduce stray WAL files.

---

## Development

```bash
uv sync --group dev

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
