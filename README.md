<div align="center">
  <img src="https://raw.githubusercontent.com/bjoernbethge/agent-farm/master/assets/farm.jpg" alt="Agent Farm" width="100%" />
</div>

# Agent Farm

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1.0+-yellow.svg)](https://duckdb.org)
[![Ollama](https://img.shields.io/badge/Ollama-Run%20Locally-white.svg)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io)
[![Query Farm](https://img.shields.io/badge/Powered%20By-Query%20Farm-orange.svg)](https://query.farm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![CI](https://github.com/bjoernbethge/agent-farm/workflows/CI/badge.svg)](https://github.com/bjoernbethge/agent-farm/actions/workflows/ci.yml)
[![Security](https://github.com/bjoernbethge/agent-farm/workflows/Security/badge.svg)](https://github.com/bjoernbethge/agent-farm/actions/workflows/security.yml)
[![Code Quality](https://github.com/bjoernbethge/agent-farm/workflows/Code%20Quality/badge.svg)](https://github.com/bjoernbethge/agent-farm/actions/workflows/code-quality.yml)

**DuckDB-powered MCP Server with a central Spec Engine for LLM agents - Web Search, Python execution, RAG, template rendering, schema validation, and more.**

[DuckDB](https://duckdb.org) | [Ollama](https://ollama.com) | [MCP Protocol](https://modelcontextprotocol.io) | [Query Farm](https://query.farm)

---

## Highlights

| Feature | Description |
|---------|-------------|
| **Spec Engine** | Central specification management with DuckDB - agents, skills, templates, schemas |
| **MCP Server** | Exposes DuckDB as an MCP server for Claude and other LLM clients |
| **Template Rendering** | MiniJinja templates for prompts, plans, and structured outputs |
| **Schema Validation** | JSON Schema validation for payloads and configurations |
| **LLM Integration** | SQL macros for calling Ollama models (local and cloud) |
| **Web Search** | DuckDuckGo and Brave Search integration |
| **Shell & Python** | Execute shell commands and Python code via UV |
| **RAG Support** | Embeddings and vector similarity search |
| **HTTP API** | Optional REST-like API via httpserver extension |
| **Multi-Org Swarm** | 5 specialized organizations with security policies |

---

## Spec Engine

The **Spec Engine** is the heart of Agent Farm - a DuckDB-based "Spec-OS" that manages all specifications:

```
┌─────────────────────────────────────────────────────────────┐
│                    Spec Engine (DuckDB)                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  minijinja  │ │ json_schema │ │  duckdb_mcp │           │
│  │ (templates) │ │ (validate)  │ │ (MCP bridge)│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  agents | skills | schemas | templates | workflows      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `spec_list` | List specs by kind (agent, skill, schema, template, etc.) |
| `spec_get` | Get a single spec by ID or kind+name |
| `spec_search` | Full-text search across specs |
| `render_from_template` | Render MiniJinja templates with context |
| `validate_payload_against_spec` | Validate JSON against schemas |

### Quick Example

```python
from agent_farm.spec_engine import get_spec_engine

engine = get_spec_engine(con)

# List all agents
agents = engine.spec_list(kind="agent")

# Get Pia (the planner agent)
pia = engine.spec_get(kind="agent", name="pia")

# Render a plan template
plan = engine.render_from_template("plan_pia_swarm", {
    "task_name": "Build User API",
    "objective": "Create REST API for users",
    "steps": [{"name": "Design", "org": "DevOrg"}],
    "success_criteria": ["Tests pass"]
})
```

See [docs/spec_engine.md](docs/spec_engine.md) for complete documentation.

---

## DuckDB Extensions

| Extension | Type | Description |
|-----------|------|-------------|
| `minijinja` | Community | MiniJinja template rendering |
| `json_schema` | Community | JSON Schema validation |
| `duckdb_mcp` | Community | MCP protocol support |
| `httpserver` | Community | HTTP OLAP API server |
| `httpfs` | Core | HTTP/S3 filesystem access |
| `json` | Core | JSON parsing and extraction |
| `vss` | Core | Vector similarity search |
| `http_client` | Community | HTTP GET/POST requests |
| `jsonata` | Community | JSONata query language |
| `shellfs` | Community | Shell command execution |

---

## Installation

**Using pip:**
```bash
pip install agent-farm
```

**Using uv (recommended):**
```bash
uv add agent-farm
```

**From source:**
```bash
git clone https://github.com/bjoernbethge/agent-farm.git
cd agent-farm
uv sync --dev
```

---

## Quick Start

**Run the MCP server:**
```bash
agent-farm
```

**With persistent database:**
```bash
DUCKDB_DATABASE=my_specs.db agent-farm
```

**With HTTP API:**
```bash
SPEC_ENGINE_HTTP_PORT=9999 SPEC_ENGINE_API_KEY=secret agent-farm
```

---

## SQL Macros

### LLM Models (via Ollama)

```sql
SELECT deepseek('Explain quantum computing');
SELECT kimi_think('Solve this step by step: ...');
SELECT qwen3_coder('Write a Python function for...');
SELECT gemini('Summarize this text...');
```

### Spec Engine

```sql
-- List specs
SELECT * FROM spec_list_by_kind('agent');
SELECT * FROM spec_search('planner');

-- Get spec details
SELECT * FROM spec_get('agent', 'pia');
SELECT spec_get_payload('skill', 'duckdb-spec-engine');

-- Render templates
SELECT spec_render_template('plan_pia_swarm', '{"task_name": "Test"}');
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');

-- Validate payloads
SELECT spec_validate('agent_config_schema', '{"name": "test", "role": "planner"}');
```

### Web Search

```sql
SELECT ddg_instant('Python programming');
SELECT ddg_abstract('machine learning');
SELECT brave_search('DuckDB tutorial');
```

### Shell & Python

```sql
SELECT shell('ls -la');
SELECT py('print(2+2)');
SELECT py_with('requests', 'import requests; print(requests.__version__)');
```

### Web Scraping

```sql
SELECT fetch('https://example.com');
SELECT fetch_text('https://example.com');
SELECT fetch_json('https://api.example.com/data');
```

### File & Git Operations

```sql
SELECT read_file('path/to/file.txt');
SELECT git_status();
SELECT git_log(10);
SELECT git_diff();
```

### RAG & Embeddings

```sql
SELECT embed('Hello world');
SELECT semantic_score('query', 'document');
SELECT rag_query('What is the price?', 'Product: Widget, Price: 49.99');
```

---

## Multi-Org Swarm

Agent Farm includes 5 specialized organizations:

| Organization | Type | Primary Model | Purpose |
|--------------|------|---------------|---------|
| **DevOrg** | dev | glm-4.7 | Code development and testing |
| **OpsOrg** | ops | kimi-k2.5 | Deployment and infrastructure |
| **ResearchOrg** | research | gpt-oss:20b | Information gathering |
| **StudioOrg** | studio | kimi-k2.5 | Creative and documentation |
| **OrchestratorOrg** | orchestrator | kimi-k2.5 | Coordination between orgs |

Each org has:
- Dedicated workspaces with security policies
- Allowed/denied tool lists
- System prompts optimized for their role

---

## Docker

```bash
docker build -t agent-farm .
docker run -v /data:/data -p 9999:9999 agent-farm
```

---

## Requirements

- Python >= 3.11
- DuckDB >= 1.1.0
- Ollama (for LLM features)

---

## GitHub Copilot Integration

### Copilot Memory with MCP

```json
{
  "mcpServers": {
    "agent-farm-memory": {
      "command": "python",
      "args": ["-m", "agent_farm"],
      "env": {
        "DUCKDB_DATABASE": ".agent_memory.db"
      }
    }
  }
}
```

### Specialized Agents

- [DevOps Agent](.github/agents/devops-agent.md) - CI/CD, Docker, security
- [Copilot Instructions](.github/copilot-instructions.md) - Repository-wide guidelines

### Path-Specific Instructions

- [`python-tests.instructions.md`](.github/instructions/python-tests.instructions.md)
- [`sql-macros.instructions.md`](.github/instructions/sql-macros.instructions.md)
- [`python-source.instructions.md`](.github/instructions/python-source.instructions.md)

---

## CI/CD & Automation

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **CI** | Push, PR | Lint, test, validate |
| **Security** | Push, PR, Weekly | CodeQL, dependency scanning |
| **Code Quality** | Push, PR | Complexity, coverage |
| **Dependencies** | Weekly | Automated updates |
| **Release** | Git tags | PyPI, Docker, GitHub releases |

```bash
# Run linting
uv run ruff check --fix src/ tests/

# Run tests
uv run pytest tests/ -v

# Build Docker image
docker build -t agent-farm .
```

---

## Documentation

- [Spec Engine](docs/spec_engine.md) - Complete Spec Engine documentation
- [Workflow Documentation](.github/WORKFLOWS.md) - CI/CD details
- [Contributing Guide](.github/CONTRIBUTING.md) - Development guidelines

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](.github/CONTRIBUTING.md) for:
- Development setup
- Coding standards
- Testing requirements
- Pull request process

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">
  <b>Happy Farming!</b>
</div>
