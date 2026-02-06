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

**DuckDB-based Spec-OS for multi-org agent swarms. Central specification management, 175+ SQL macros, meta-learning, MCP Apps, and smart extensions.**

[DuckDB](https://duckdb.org) | [Ollama](https://ollama.com) | [MCP Protocol](https://modelcontextprotocol.io) | [Query Farm](https://query.farm)

---

## The Story

Agent Farm evolved from a tool suite into a **Spec-OS** — a specification operating system for coordinating AI agent swarms across organizations.

**Timeline:**
- **Dec 8, 2025:** Foundation (DuckDB + Ollama + MCP)
- **Dec 8-16, 2025:** Power macros (web search, shell, Python, git)
- **Feb 2-4, 2026:** Spec Engine revolution (central spec management + meta-learning + intelligence layer)
- **Feb 6, 2026:** Production ready (initialization fixes, all macros validated)

**Why it matters:**
Agent Farm answers: **"How do you coordinate multi-org agent swarms with shared spec management?"**

Built on 17+ years of enterprise experience (VWAG, NVIDIA, Adidas), now open source. Not inventing theory — open-sourcing what works in production. This is the proof that **Production Experience → Better Open Source**.

See [`dev/agent-farm-story.md`](../../dev/agent-farm-story.md) for the full history, architecture, and why it's critical infrastructure for agentic-dev-io.

---

## Highlights

| Feature | Description |
|---------|-------------|
| **Spec Engine** | Central specification management (agents, skills, templates, schemas, workflows, orgs) |
| **175+ SQL Macros** | LLM calls, web search, shell, Python, file ops, git, RAG, agent harness |
| **Multi-Org Swarm** | 5 specialized orgs with security policies, tool permissions, and denial rules |
| **MCP Server** | Exposes DuckDB as an MCP server via `duckdb_mcp` extension |
| **MCP Apps** | 11+ MiniJinja-based UI templates (Vibe Coder, Approval Flow, Model Selector, etc.) |
| **Agent Harness** | Full agent loop with tool execution, supporting Ollama and Anthropic backends |
| **Meta-Learning** | Feedback tracking, spec adaptations, confidence scoring, learning insights |
| **Intelligence Layer** | Embeddings storage, org-specific knowledge bases, hybrid search (vector + keyword) |
| **Smart Extensions** | JSONata, DuckPGQ graphs, Bitfilters, Lindel spatial, LSH near-dedup, Radio pub/sub |
| **Template Rendering** | MiniJinja templates for prompts, plans, and structured outputs |
| **Schema Validation** | JSON Schema validation for payloads and configurations |
| **HTTP API** | Optional REST-like API via `httpserver` extension |

---

## Architecture

```
agent-farm/
├── src/agent_farm/             # Main Python package
│   ├── main.py                 # Entry point, MCP server initialization
│   ├── spec_engine.py          # Spec Engine class (central component)
│   ├── orgs.py                 # Organization configurations (5 orgs)
│   ├── schemas.py              # Data models, enums, SQL table definitions
│   ├── udfs.py                 # Python UDFs (agent_chat, agent_tools, etc.)
│   └── sql/                    # Modular SQL macros (175+)
│       ├── 01_base.sql         # Base utilities (url_encode, timestamps)
│       ├── 02_ollama.sql       # LLM model macros (Ollama + cloud wrappers)
│       ├── 03_tools.sql        # Web search, shell, Python, fetch, file, git
│       ├── 04_agent.sql        # Security policies, audit, secure ops, injection detection
│       ├── 05_harness.sql      # Agent harness (Anthropic + Ollama routing, tool execution)
│       ├── 06_orgs.sql         # Org tables, permissions, orchestrator routing
│       ├── 07_org_tools.sql    # Org-specific tools (SearXNG, CI/CD, notes, render jobs)
│       ├── 08_mcp_apps.sql     # MCP Apps system (11+ templates, onboarding, settings)
│       └── 09_smart_extensions.sql  # Smart extensions (JSONata, DuckPGQ, Bitfilters, etc.)
├── db/                         # Spec Engine SQL files
│   ├── spec_engine_schema.sql  # Core schema (7 tables, 19 views, 7 sequences)
│   ├── spec_engine_macros.sql  # 50+ spec query/mutation/template/validation macros
│   ├── spec_engine_seed.sql    # Seed data (agents, skills, templates, schemas, orgs, workflows)
│   ├── spec_engine_intelligence.sql  # Intelligence layer (embeddings, knowledge bases)
│   ├── spec_engine_rag.sql     # RAG/hybrid search macros
│   ├── spec_engine_http.sql    # HTTP API views
│   └── spec_engine_init.sql    # Extension loading
├── scripts/                    # Utility scripts
│   ├── install_extensions.py
│   └── test_extensions.py
├── tests/                      # Test suite
├── docs/                       # Documentation
├── mcp.json                    # MCP server configuration
├── Dockerfile                  # Docker build
└── pyproject.toml              # Project config (uv_build)
```

---

## Spec Engine

The **Spec Engine** is the heart of Agent Farm - a DuckDB-based "Spec-OS" that manages all specifications:

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Spec Engine (DuckDB)                            │
│  ┌───────────┐ ┌─────────────┐ ┌───────────┐ ┌────────────────────┐ │
│  │ minijinja │ │ json_schema │ │ duckdb_mcp│ │ 15+ more extensions│ │
│  │(templates)│ │ (validate)  │ │(MCP bridge)│ │  (optional)        │ │
│  └───────────┘ └─────────────┘ └───────────┘ └────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  agents | skills | schemas | templates | workflows | orgs        ││
│  │  apis | protocols | mcp_servers | ui | relationships             ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  meta-learning: feedback | adaptations | learnings | confidence  ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  intelligence: embeddings | knowledge_dev/research/studio/ops    ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### Spec Kinds

| Kind | Description | Example |
|------|-------------|---------|
| `agent` | Agent specifications | Pia (planner), org agents |
| `skill` | Skill/capability definitions | duckdb-spec-engine, surrealdb-memory |
| `schema` | JSON Schemas for validation | agent_config_schema, task_template_schema |
| `task_template` | MiniJinja task templates | plan_pia_swarm |
| `prompt_template` | Prompt templates | agent_system_prompt |
| `api` | API specifications | openai-chat-completions |
| `protocol` | Protocol specs | MCP |
| `org` | Organization specs | DevOrg, OpsOrg, etc. |
| `workflow` | Multi-step workflows | agent_onboarding |
| `ui` | UI components (Open Response) | plan_viewer |
| `mcp_server` | MCP server definitions | agent-farm, filesystem, brave-search |

### MCP Tools

| Tool | Description |
|------|-------------|
| `spec_list` | List specs by kind with optional filters |
| `spec_get` | Get a single spec by ID or kind+name |
| `spec_search` | Full-text search across specs |
| `render_from_template` | Render MiniJinja templates with context |
| `validate_payload_against_spec` | Validate JSON against schemas |
| `mcp_query_remote` | Query remote MCP servers |
| `mcp_call_remote_tool` | Call remote MCP tools |

### Python API

```python
from agent_farm.spec_engine import get_spec_engine
import duckdb

con = duckdb.connect(":memory:")
engine = get_spec_engine(con)

# List all agents
agents = engine.spec_list(kind="agent")

# Get Pia (the planner agent)
pia = engine.spec_get(kind="agent", name="pia")

# Render a plan template
plan = engine.render_from_template("plan_pia_swarm", {
    "task_name": "Build User API",
    "objective": "Create REST API for users",
    "steps": [{"name": "Design", "org": "DevOrg", "tool": "spec_get", "input": {}, "expected_output": "API spec"}],
    "success_criteria": ["Tests pass"]
})

# Meta-learning: record usage feedback
engine.record_feedback(spec_id=10, feedback_type="success", score=0.9)

# Intelligence: store and search embeddings
engine.store_embedding(content="API design doc", embedding=[0.1, 0.2, ...], content_type="doc")
engine.search_similar(query_embedding=[0.1, 0.2, ...], k=5)
```

See [docs/spec_engine.md](docs/spec_engine.md) for complete documentation.

---

## SQL Macros (175+)

### LLM Models (via Ollama)

```sql
-- Cloud model wrappers (routed through Ollama)
SELECT deepseek('Explain quantum computing');
SELECT kimi('Summarize this paper...');
SELECT kimi_think('Solve this step by step: ...');
SELECT qwen3_coder('Write a Python function for...');
SELECT gemini('Summarize this text...');
SELECT glm('Translate to German: ...');
SELECT minimax('Creative writing prompt...');
SELECT gpt_oss('Analyze this data...');

-- With tool calling
SELECT deepseek_tools('Find the weather', '[{"type": "function", ...}]');
SELECT kimi_tools('Search for...', tools_json);

-- Raw Ollama API
SELECT ollama_chat('llama3.2', 'Hello!');
SELECT ollama_embed('nomic-embed-text', 'text to embed');

-- Embeddings & RAG
SELECT embed('Hello world');
SELECT semantic_score('query', 'document');
SELECT rag_query('What is the price?', 'Product: Widget, Price: 49.99');
SELECT cosine_sim(vec1, vec2);
```

### Spec Engine

```sql
-- List and search specs
SELECT * FROM spec_list_by_kind('agent');
SELECT * FROM spec_search('planner');
SELECT * FROM spec_list_active();

-- Get spec details
SELECT * FROM spec_get('agent', 'pia');
SELECT spec_get_payload('skill', 'duckdb-spec-engine');
SELECT spec_get_doc('agent', 'pia');

-- Render templates
SELECT spec_render_template('plan_pia_swarm', '{"task_name": "Test"}');
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');

-- Validate payloads
SELECT spec_validate('agent_config_schema', '{"name": "test", "role": "planner"}');
SELECT spec_is_valid('agent_config_schema', '{"name": "test", "role": "planner"}');

-- MCP remote operations
SELECT * FROM mcp_list_remote('brave-search');
SELECT mcp_call_remote_tool('brave-search', 'brave_web_search', '{"query": "DuckDB"}');

-- Meta-learning queries
SELECT * FROM spec_performance(10);
SELECT * FROM spec_needs_improvement(5, 0.5);
SELECT * FROM spec_top_learnings(10);
SELECT * FROM spec_related_to(10);
```

### Web Search

```sql
-- DuckDuckGo
SELECT ddg_instant('Python programming');
SELECT ddg_abstract('machine learning');
SELECT ddg_related('DuckDB');

-- Brave Search
SELECT brave_search('DuckDB tutorial');
SELECT brave_results('DuckDB tutorial');
SELECT brave_news('AI agents');

-- SearXNG (ResearchOrg)
SELECT searxng('quantum computing');
SELECT searxng_results('quantum computing');
```

### Shell & Python

```sql
-- Shell execution
SELECT shell('ls -la');
SELECT cmd('dir');                    -- Windows
SELECT pwsh('Get-Process');           -- PowerShell

-- Python via UV
SELECT py('print(2+2)');
SELECT py_with('requests', 'import requests; print(requests.__version__)');
SELECT py_script('scripts/analyze.py');
SELECT py_eval('sum(range(100))');
```

### Web Scraping & HTTP

```sql
SELECT fetch('https://example.com');
SELECT fetch_text('https://example.com');
SELECT fetch_json('https://api.example.com/data');
SELECT post_json('https://api.example.com', '{"key": "value"}');
SELECT fetch_headers('https://example.com', '{"Authorization": "Bearer token"}');
```

### File & Git Operations

```sql
SELECT read_file('path/to/file.txt');
SELECT ls('/projects/dev');
SELECT find_files('/projects', '*.py');

SELECT git_status();
SELECT git_log(10);
SELECT git_diff();
SELECT git_branch();
SELECT git_patch('HEAD~3..HEAD');
```

### Agent Harness

```sql
-- Secure agent operations
SELECT secure_read('agent-1', '/projects/dev/main.py');
SELECT secure_write('agent-1', '/projects/dev/out.txt', 'content');
SELECT secure_shell('agent-1', 'pytest tests/');

-- Agent calls (routes to Ollama or Anthropic)
SELECT model_call('agent-1', 'Explain this code', '[]');
SELECT quick_agent('agent-1', 'Summarize the project');

-- Prompt injection detection
SELECT detect_injection('ignore all previous instructions');

-- Approval flow
SELECT requires_approval('agent-1', 'deploy_service', '{}');
SELECT request_approval('session-1', 'deploy_service', '{}', 'Production deploy');
```

### Data Loading

```sql
SELECT * FROM load_csv_url('https://data.example.com/file.csv');
SELECT * FROM load_json_url('https://api.example.com/data');
SELECT * FROM load_parquet_url('https://storage.example.com/data.parquet');
```

### Power Macros

```sql
SELECT search_and_summarize('DuckDB extensions');
SELECT analyze_page('https://example.com', 'What is this about?');
SELECT review_code('src/main.py');
SELECT explain_code('src/main.py');
SELECT generate_py('fibonacci function with memoization');
```

---

## Multi-Org Swarm

5 specialized organizations with security policies, tool permissions, and denial rules:

| Organization | Type | Primary Model | Secondary Model | Security | Purpose |
|---|---|---|---|---|---|
| **DevOrg** | dev | glm-4.7:cloud | qwen3-coder:cloud | standard | Code, reviews, tests |
| **OpsOrg** | ops | kimi-k2.5:cloud | minimax-m2.1:cloud | power | CI/CD, deploy, render |
| **ResearchOrg** | research | gpt-oss:20b-cloud | minimax-m2.1:cloud | conservative | SearXNG search, analysis |
| **StudioOrg** | studio | kimi-k2.5:cloud | gemma3:4b-cloud | standard | Specs, docs, DCC briefings |
| **OrchestratorOrg** | orchestrator | kimi-k2.5:cloud | glm-4.7:cloud | conservative | Task routing, coordination |

Each org has:
- Dedicated workspaces with security policies
- Allowed/denied tool lists with approval requirements
- System prompts optimized for their role
- Smart extension integrations (JSONata, DuckPGQ, Bitfilters, Lindel, LSH, Radio)

### Org Routing

```sql
-- Orchestrator delegates to orgs
SELECT call_org('orchestrator-org', 'dev-org', 'session-1', 'Write unit tests');

-- Smart routing based on task type
SELECT smart_route('orchestrator-org', 'code_review', '{"file": "main.py"}');

-- Check permissions
SELECT is_org_tool_allowed('dev-org', 'fs_write');
SELECT is_org_action_denied('dev-org', 'workspace', '/projects/ops/secret');
```

---

## MCP Apps

11+ MiniJinja-based UI templates rendered server-side:

| App | Description |
|-----|-------------|
| **Vibe Coder** | AI-assisted code generation interface |
| **Solid Docs** | Documentation generator (README, API docs) |
| **Approval Flow** | Human-in-the-loop approval UI |
| **Model Selector** | LLM model comparison and selection |
| **Terminal** | Terminal output viewer |
| **Document Viewer** | Markdown/text document viewer |
| **Chart Viewer** | Data visualization |
| **Immersive Preview** | Image/media preview |
| **Design Choices** | Design decision presenter |
| **Profile Choices** | Onboarding profile selector |
| **Base Template** | Foundation template for custom apps |

```sql
-- Open an app
SELECT open_app('vibe-coder', 'session-1', '{"code": "def hello():", "prompt": "Add docstring"}');

-- Studio apps
SELECT studio_present_choices('session-1', 'API Design', 'Choose approach', '[{"id": "rest", "label": "REST"}]');
SELECT studio_open_preview('session-1', 'image', 'https://example.com/preview.png', '{}');

-- Approval flow
SELECT open_approval_ui('session-1', 'Deploy to Production', 'Deploy user-service v2.1', '{}', 75);
```

---

## Smart Extensions

Advanced DuckDB extensions integrated per organization:

| Extension | Orgs | Purpose |
|-----------|------|---------|
| **JSONata** | Research, Dev | JSON query/transform for API response parsing |
| **DuckPGQ** | Orchestrator | Property graphs for task dependencies and org relationships |
| **Bitfilters** | Ops, Research | Bloom/MinHash for log dedup and similarity detection |
| **Lindel** | Research, Studio | Space-filling curves for embedding indexing and asset ordering |
| **LSH** | Research | Locality Sensitive Hashing for near-duplicate document detection |
| **Radio** | Orchestrator, Ops, Studio | WebSocket/Redis pub/sub for real-time sync |

```sql
-- JSONata transform
SELECT json_transform('{"items": [1,2,3]}', '$sum(items)');

-- Graph queries (DuckPGQ)
SELECT orchestrator_find_path('dev-org', 'ops-org');
SELECT orchestrator_get_ready_tasks();

-- Dedup (Bitfilters)
SELECT ops_is_duplicate('ci-logs', 'Build failed: timeout');

-- Near-duplicate detection (LSH)
SELECT research_find_similar_docs('quantum computing overview', 0.8, 10);

-- Real-time events (Radio)
SELECT orchestrator_broadcast('tasks', '{"type": "new_task", "org": "dev-org"}');
```

---

## Intelligence Layer

Org-specific knowledge bases with embedding storage and hybrid search:

| Knowledge Base | Organization | Content |
|---|---|---|
| `spec_embeddings` | All | General embedding storage with content types |
| `knowledge_dev` | DevOrg | Code snippets, AST types, docstrings |
| `knowledge_research` | ResearchOrg | Search results, source URLs, relevance scores |
| `knowledge_studio` | StudioOrg | Design decisions, rationale, performance |
| `knowledge_ops` | OpsOrg | Pipeline logs, metrics, durations |
| `memory_conversations` | All | Conversation history with importance scoring |

```sql
-- Vector similarity search
SELECT * FROM vss_search_embeddings(embed('API design'), 10, 'doc');

-- Hybrid search (keyword + vector)
SELECT * FROM vss_hybrid_search('REST API', embed('REST API'), 10);
```

---

## Meta-Learning

The Spec Engine tracks usage, feedback, and adaptations to improve over time:

```python
# Record that a spec was used successfully
engine.record_usage(spec_id=10, was_success=True)

# Record detailed feedback
engine.record_feedback(
    spec_id=10,
    feedback_type="success",
    score=0.9,
    context={"task": "API design"},
    notes="Plan was clear and actionable"
)

# Find specs that need improvement
weak_specs = engine.get_specs_needing_improvement(min_usage=5, max_success_rate=0.5)

# Record an adaptation
engine.record_adaptation(
    spec_id=10,
    adaptation_type="prompt_improve",
    reason="Low success rate on complex tasks",
    changes={"system_prompt": "Updated to include more structure"}
)

# Record a learning insight
engine.record_learning(
    learning_type="pattern",
    category="agent",
    description="Planner agents work better with explicit step numbering",
    confidence=0.8
)
```

---

## DuckDB Extensions

| Extension | Type | Required | Description |
|-----------|------|----------|-------------|
| `json` | Core | Yes | JSON parsing and extraction |
| `minijinja` | Community | Yes | MiniJinja template rendering |
| `json_schema` | Community | Yes | JSON Schema validation |
| `duckdb_mcp` | Community | Yes | MCP protocol support |
| `httpfs` | Core | Yes | HTTP/S3 filesystem access |
| `http_client` | Community | Yes | HTTP GET/POST requests |
| `icu` | Core | Yes | Unicode support |
| `httpserver` | Community | No | HTTP OLAP API server |
| `ducklake` | Community | No | Persistent lakehouse with time travel |
| `vss` | Core | No | Vector similarity search |
| `fts` | Core | No | Full-text search |
| `jsonata` | Community | No | JSONata query language |
| `duckpgq` | Community | No | Property graphs |
| `bitfilters` | Community | No | Bloom/MinHash filters |
| `lindel` | Community | No | Space-filling curves |
| `htmlstringify` | Community | No | HTML to text for scraping |
| `lsh` | Community | No | Locality Sensitive Hashing |
| `shellfs` | Community | No | Shell commands as tables |
| `zipfs` | Community | No | ZIP archive access |
| `radio` | Community | No | WebSocket & Redis pub/sub |

---

## Python UDFs

Registered as DuckDB functions via `udfs.py`:

| UDF | Description |
|-----|-------------|
| `agent_chat(model, prompt, system_prompt)` | Chat with Ollama or Anthropic models |
| `agent_tools(model, prompt, tools_json, system_prompt)` | Chat with tool calling |
| `detect_injection_udf(content)` | Detect prompt injection patterns |
| `safe_json_extract(json_str, path)` | Safe JSON path extraction |

Spec Engine UDFs (from `spec_engine.py`):

| UDF | Description |
|-----|-------------|
| `spec_list_udf(kind, status, limit)` | List specs |
| `spec_search_udf(query, limit)` | Search specs |
| `render_template_udf(template_name, context_json)` | Render template |
| `validate_payload_udf(kind, name, payload_json)` | Validate payload |

---

## Installation

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

## MCP Client Configuration

```json
{
  "mcpServers": {
    "agent-farm": {
      "command": "agent-farm",
      "args": [],
      "env": {
        "DUCKDB_DATABASE": ".agent_memory.db"
      }
    }
  }
}
```

---

## Docker

```bash
docker build -t agent-farm .
docker run -v /data:/data -p 9999:9999 agent-farm
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Database path | `:memory:` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | None |
| `SPEC_ENGINE_API_KEY` | HTTP API key | None |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `BRAVE_API_KEY` | Brave Search API key | None |

---

## Requirements

- Python >= 3.11
- DuckDB >= 1.1.0
- Ollama (for LLM features)

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

# Run with coverage
uv run pytest tests/ --cov=src/agent_farm
```

---

## GitHub Copilot Integration

### Specialized Agents

- [DevOps Agent](.github/agents/devops-agent.md) - CI/CD, Docker, security
- [Copilot Instructions](.github/copilot-instructions.md) - Repository-wide guidelines

### Path-Specific Instructions

- [`python-tests.instructions.md`](.github/instructions/python-tests.instructions.md)
- [`sql-macros.instructions.md`](.github/instructions/sql-macros.instructions.md)
- [`python-source.instructions.md`](.github/instructions/python-source.instructions.md)

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
