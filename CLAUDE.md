# Claude Code Instructions

This file provides context and instructions for AI agents (Claude, Copilot, etc.) working with the Agent Farm codebase.

## Project Overview

**Agent Farm** is a DuckDB-powered MCP server with a central **Spec Engine** that manages specifications for LLM agents. It provides:

- Unified specification storage (agents, skills, templates, schemas, workflows, orgs, APIs, protocols, UI, MCP servers)
- 175+ SQL macros (LLM calls, web search, shell, Python, file ops, git, RAG, agent harness)
- Multi-org agent swarm (5 orgs with security policies, tool permissions, denial rules)
- MCP Apps system (11+ MiniJinja UI templates)
- Agent harness with Ollama + Anthropic backends
- Meta-learning (feedback, adaptations, confidence tracking, learning insights)
- Intelligence layer (embeddings, org-specific knowledge bases, hybrid search)
- Smart extensions (JSONata, DuckPGQ, Bitfilters, Lindel, LSH, Radio)
- Template rendering via MiniJinja
- JSON Schema validation
- MCP protocol integration via `duckdb_mcp`
- Optional HTTP API via `httpserver`

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
│       ├── 02_ollama.sql       # LLM model macros (31 macros)
│       ├── 03_tools.sql        # Web search, shell, Python, fetch, file, git (43 macros)
│       ├── 04_agent.sql        # Security policies, audit, secure ops, injection detection (25 macros)
│       ├── 05_harness.sql      # Agent harness, Anthropic + Ollama routing (15 macros)
│       ├── 06_orgs.sql         # Org tables, permissions, orchestrator routing (16 macros)
│       ├── 07_org_tools.sql    # SearXNG, CI/CD, notes board, render jobs (~30 macros)
│       ├── 08_mcp_apps.sql     # MCP Apps, templates, onboarding, settings (50+ macros)
│       └── 09_smart_extensions.sql  # JSONata, DuckPGQ, Bitfilters, Lindel, LSH, Radio (25+ macros)
├── db/                         # Spec Engine SQL files
│   ├── spec_engine_schema.sql  # Core schema (7 tables, 19 views, 7 sequences)
│   ├── spec_engine_macros.sql  # 50+ spec query/mutation/template/validation macros
│   ├── spec_engine_seed.sql    # Seed data (agents, skills, templates, schemas, orgs, workflows)
│   ├── spec_engine_intelligence.sql  # Intelligence layer (embeddings, org knowledge bases)
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

## Key Components

### 1. Spec Engine (`src/agent_farm/spec_engine.py`)

The central specification management system. Key methods:

```python
# Query operations
spec_list(kind, status, limit)      # List specs by kind
spec_get(id, kind, name, version)   # Get single spec
spec_search(query, limit)           # Search specs

# Template rendering
render_from_template(template_name, context)

# Validation
validate_payload_against_spec(kind, name, payload)

# CRUD operations
spec_create(kind, name, summary, ...)
spec_update(id, status, summary, doc, payload)
spec_delete(id)

# Meta-learning
record_usage(spec_id, was_success)
record_feedback(spec_id, feedback_type, score, context, outcome, notes)
record_adaptation(spec_id, adaptation_type, reason, changes)
record_learning(learning_type, category, description, evidence, confidence)
get_specs_needing_improvement(min_usage, max_success_rate)
get_spec_performance(spec_id)
get_top_learnings(limit)

# Relationships & provenance
create_relationship(from_id, to_id, rel_type, metadata)
get_related_specs(spec_id)
set_upstream_source(spec_id, source_url, upstream_version, source_ref)
get_specs_needing_sync()

# Intelligence layer
store_embedding(content, embedding, content_type, spec_id, org_id, metadata)
search_similar(query_embedding, k, content_type)
hybrid_search(text_query, query_embedding, k, content_type, keyword_weight)
store_conversation_memory(session_id, role, content, embedding, importance)
get_conversation_context(session_id, k)
store_org_knowledge(org, content, embedding, **kwargs)
get_knowledge_stats()

# Utilities
get_stats()
get_loaded_extensions()
get_spec_kinds()

# HTTP server
start_http_server(port, api_key)
stop_http_server()
```

### 2. SQL Macros (`src/agent_farm/sql/` + `db/`)

175+ SQL macros organized across 9 modular files:

- **01_base.sql**: `get_secret`, `url_encode`, `now_iso`, `now_unix`
- **02_ollama.sql**: `ollama_chat`, `deepseek`, `kimi`, `kimi_think`, `gemini`, `qwen3_coder`, `glm`, `minimax`, `gpt_oss`, `embed`, `semantic_score`, `rag_query`, `cosine_sim`, tool-calling variants
- **03_tools.sql**: `ddg_instant`, `brave_search`, `searxng`, `shell`, `cmd`, `pwsh`, `py`, `py_with`, `fetch`, `fetch_json`, `post_json`, `read_file`, `ls`, `git_status`, `git_log`, `git_diff`, `load_csv_url`, `search_and_summarize`, `review_code`, `explain_code`, `generate_py`
- **04_agent.sql**: `secure_read`, `secure_write`, `secure_shell`, `detect_injection`, `log_tool_call`, `is_allowed_path`, `requires_approval`
- **05_harness.sql**: `model_call`, `agent_step`, `quick_agent`, `anthropic_chat`, `agent_tools_schema`, `execute_tool_safe`
- **06_orgs.sql**: `get_org_prompt`, `is_org_tool_allowed`, `call_org`, `orchestrator_tools_schema`
- **07_org_tools.sql**: `searxng_search`, `ci_trigger`, `deploy_service`, `notes_board_create`, `test_run`, `git_patch`, `execute_org_tool`
- **08_mcp_apps.sql**: `render_app`, `open_app`, `studio_present_choices`, `dev_open_vibe_coder`, `open_approval_ui`, `open_model_selector`, `smart_execute_tool`
- **09_smart_extensions.sql**: `json_transform`, `orchestrator_find_path`, `ops_is_duplicate`, `research_find_similar_docs`, `orchestrator_broadcast`, `smart_route`

Spec Engine macros (`db/spec_engine_macros.sql`):
- `spec_list_by_kind`, `spec_search`, `spec_get`, `spec_get_payload`, `spec_get_doc`
- `spec_render_template`, `spec_render`, `spec_validate`, `spec_is_valid`
- `mcp_list_remote`, `mcp_call_remote_tool`
- `spec_performance`, `spec_needs_improvement`, `spec_top_learnings`, `spec_related_to`
- `spec_http_start`, `spec_http_stop`, `spec_stats`

### 3. Organizations (`src/agent_farm/orgs.py`)

5 specialized organizations:

| Org | Primary Model | Secondary Model | Security | Role |
|-----|--------------|-----------------|----------|------|
| **DevOrg** | glm-4.7:cloud | qwen3-coder:cloud | standard | Code, reviews, tests |
| **OpsOrg** | kimi-k2.5:cloud | minimax-m2.1:cloud | power | CI/CD, deploy, render |
| **ResearchOrg** | gpt-oss:20b-cloud | minimax-m2.1:cloud | conservative | SearXNG search, analysis |
| **StudioOrg** | kimi-k2.5:cloud | gemma3:4b-cloud | standard | Specs, docs, DCC briefings |
| **OrchestratorOrg** | kimi-k2.5:cloud | glm-4.7:cloud | conservative | Task routing, coordination |

Each org has: dedicated workspaces, allowed/denied tool lists, approval requirements, smart extension integrations, system prompts.

### 4. Python UDFs (`src/agent_farm/udfs.py`)

- `agent_chat(model, prompt, system_prompt)` - Chat via Ollama or Anthropic
- `agent_tools(model, prompt, tools_json, system_prompt)` - Chat with tool calling
- `detect_injection_udf(content)` - Prompt injection detection
- `safe_json_extract(json_str, path)` - Safe JSON extraction

### 5. DuckDB Extensions

Required: `json`, `minijinja`, `json_schema`, `duckdb_mcp`, `httpfs`, `http_client`, `icu`

Optional: `httpserver`, `ducklake`, `vss`, `fts`, `jsonata`, `duckpgq`, `bitfilters`, `lindel`, `htmlstringify`, `lsh`, `shellfs`, `zipfs`, `radio`

### 6. Spec Kinds

`agent`, `skill`, `schema`, `task_template`, `prompt_template`, `api`, `protocol`, `org`, `workflow`, `ui`, `mcp_server`

## Development Guidelines

### Code Style

- Python 3.11+ with type hints
- 100 character line limit (ruff)
- Use uv for all package management
- Follow existing patterns in codebase
- No god classes - split into focused modules

### SQL Macros

- Use `CREATE OR REPLACE MACRO` for all macros
- Include clear comments
- Use parameterized queries to prevent injection
- Handle NULL cases appropriately

### Testing

```bash
uv run pytest tests/ -v
uv run pytest tests/test_spec_engine.py -v
uv run pytest tests/ --cov=src/agent_farm
```

### Adding New Features

1. **New Spec Kind**: Add to seed data in `db/spec_engine_seed.sql`
2. **New SQL Macro**: Add to appropriate file in `src/agent_farm/sql/`
3. **New Spec Engine Method**: Add to `src/agent_farm/spec_engine.py`
4. **New MCP Tool**: Register in `register_spec_engine_tools()`
5. **New Smart Extension**: Add to `src/agent_farm/sql/09_smart_extensions.sql`
6. **New MCP App**: Add template + macros to `src/agent_farm/sql/08_mcp_apps.sql`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_DATABASE` | Database path | `:memory:` |
| `SPEC_ENGINE_HTTP_PORT` | HTTP server port | None |
| `SPEC_ENGINE_API_KEY` | HTTP API key | None |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `BRAVE_API_KEY` | Brave Search API key | None |

## Important Notes

1. **Spec Engine is the core** - All specifications go through the Spec Engine
2. **Extensions may fail** - Handle extension loading errors gracefully (required vs optional)
3. **JSON stored as VARCHAR** - For DuckDB compatibility
4. **MiniJinja syntax** - Templates use Jinja2-like syntax via MiniJinja
5. **Schema validation** - Use `json_schema` extension for validation
6. **Meta-learning** - The system tracks usage, feedback, and adaptations
7. **Org security** - Each org has strict tool permissions and denial rules
8. **Build system** - Uses `uv_build`, not setuptools

## Links

- [Spec Engine Documentation](docs/spec_engine.md)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [MiniJinja Documentation](https://docs.rs/minijinja/latest/minijinja/)
- [JSON Schema](https://json-schema.org/)
- [MCP Protocol](https://modelcontextprotocol.io/)
