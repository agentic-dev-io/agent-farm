# SQL Macro Reference (280+)

All macros are loaded at startup from `src/agent_farm/sql/`. They are available in the REPL via `SELECT macro_name(...)` and from any SQL file.

---

## base.sql — Core Utilities (4)

| Macro | Signature | Description |
|-------|-----------|-------------|
| `get_secret` | `(name)` | Returns a secret value (mock; replace with vault integration) |
| `url_encode` | `(str)` | URL-encodes a string (spaces, `&`, `=`, `?`, `#`, `%`) |
| `now_iso` | `()` | Current timestamp as ISO-8601 string (`2024-01-01T12:00:00Z`) |
| `now_unix` | `()` | Current timestamp as Unix epoch float |

---

## ollama.sql — LLM & Embeddings (28)

### Core API

| Macro | Signature | Description |
|-------|-----------|-------------|
| `ollama_base` | `()` | Ollama base URL (`OLLAMA_BASE_URL` env or `http://localhost:11434`) |
| `ollama_chat` | `(model_name, prompt)` | Single-turn chat via `/api/generate` |
| `ollama_chat_messages` | `(model_name, messages_json)` | Multi-turn chat via `/api/chat` |
| `ollama_chat_with_tools` | `(model_name, messages_json, tools_json)` | Chat with tool-calling support |
| `ollama_embed` | `(model_name, text_input)` | Generate embedding vector (`FLOAT[]`) |
| `extract_tool_calls` | `(response_body)` | Extract `tool_calls` array from response |
| `extract_response` | `(response_body)` | Extract text content from response |
| `has_tool_calls` | `(response_body)` | Returns `TRUE` if response contains tool calls |
| `agent_call` | `(model_name, system_prompt, user_prompt, tools_json)` | Structured agent call with system prompt |
| `cosine_sim` | `(vec1, vec2)` | Cosine similarity between two `FLOAT[]` vectors |
| `embed` | `(text_input)` | Embed text with `nomic-embed-text` |
| `semantic_score` | `(query_text, doc_text)` | Cosine similarity between two embedded texts |
| `rag_query` | `(question, context)` | Answer question from context using DeepSeek |
| `rag_think` | `(question, context)` | Deep reasoning over context using Kimi-Think |

### Model Shortcuts

| Macro | Model |
|-------|-------|
| `deepseek(prompt)` | `deepseek-v3.2:cloud` |
| `kimi(prompt)` | `kimi-k2.5:cloud` |
| `kimi_think(prompt)` | `kimi-k2-thinking:cloud` |
| `gemini(prompt)` | `gemini-3-pro-preview:latest` |
| `gemini_flash(prompt)` | `gemini-3-flash-preview:latest` |
| `qwen3_coder(prompt)` | `qwen3-coder-next:cloud` |
| `qwen3_vl(prompt)` | `qwen3-vl:235b-cloud` |
| `qwen(prompt)` | `qwen3.5:cloud` |
| `glm(prompt)` | `glm-5:cloud` |
| `minimax(prompt)` | `minimax-m2.5:cloud` |
| `gpt_oss(prompt)` | `gpt-oss:120b-cloud` |
| `gpt_oss_small(prompt)` | `gpt-oss:20b-cloud` |
| `gpt_codex(prompt)` | `gpt-5.3-codex:latest` |
| `devstral(prompt)` | `devstral-2:123b-cloud` |

---

## tools.sql — Web, Shell, Files, Git (48)

### Web Search

| Macro | Signature | Description |
|-------|-----------|-------------|
| `ddg_instant` | `(query)` | DuckDuckGo Instant Answer API (full JSON) |
| `ddg_abstract` | `(query)` | DuckDuckGo abstract text |
| `ddg_related` | `(query)` | DuckDuckGo related topics |
| `ddg_definition` | `(query)` | DuckDuckGo definition |
| `brave_search` | `(query)` | Brave Web Search (requires `BRAVE_API_KEY`) |
| `brave_results` | `(query)` | Brave search results array |
| `brave_news` | `(query)` | Brave News Search |

### Shell / Command Execution

| Macro | Signature | Description |
|-------|-----------|-------------|
| `shell` | `(cmd)` | Run shell command, return stdout (Linux/macOS) |
| `shell_csv` | `(cmd)` | Run command, return result as table (CSV) |
| `shell_json` | `(cmd)` | Run command, return result as table (JSON) |
| `cmd` | `(command)` | Windows `cmd /c` execution |
| `pwsh` | `(command)` | PowerShell execution |

### Python / UV Execution

| Macro | Signature | Description |
|-------|-----------|-------------|
| `py` | `(code)` | Run Python code snippet via `uv run python -c` |
| `py_with` | `(deps, code)` | Run Python with extra packages (`uv run --with`) |
| `py_script` | `(script_path)` | Execute a Python script file |
| `py_script_args` | `(script_path, args)` | Execute Python script with arguments |
| `py_eval` | `(expr)` | Evaluate a Python expression and return result |

### Web Fetch / HTTP

| Macro | Signature | Description |
|-------|-----------|-------------|
| `web_fetch` | `(url)` | HTTP GET, return raw body |
| `fetch_text` | `(url)` | HTTP GET, return body as text |
| `fetch_json` | `(url)` | HTTP GET, return body as JSON |
| `fetch_headers` | `(url, headers_map)` | HTTP GET with custom headers |
| `fetch_ua` | `(url)` | HTTP GET with browser User-Agent |
| `post_json` | `(url, body_json)` | HTTP POST with JSON body |
| `post_form` | `(url, form_data)` | HTTP POST with form-encoded body |

### File Operations

| Macro | Signature | Description |
|-------|-----------|-------------|
| `read_file` | `(path)` | Read file contents as text |
| `ls` | `(path)` | `ls -la` directory listing |
| `dir_list` | `(path)` | Windows `dir` listing |
| `find_files` | `(path, pattern)` | `find` by name pattern (Linux/macOS) |
| `find_win` | `(path, pattern)` | Windows `dir /s /b` search |
| `cat_files` | `(pattern)` | Read multiple files matching glob pattern (TABLE) |

### Git Operations

| Macro | Signature | Description |
|-------|-----------|-------------|
| `git_status` | `()` | `git status` output |
| `git_log` | `(n)` | Last N commits (`--oneline`) |
| `git_diff` | `()` | `git diff` output |
| `git_branch` | `()` | `git branch -a` output |

### System Info

| Macro | Signature | Description |
|-------|-----------|-------------|
| `sys_info` | `()` | OS, machine, Python version as JSON |
| `env_var` | `(name)` | Read env variable (Linux/macOS via `printenv`) |
| `env_var_win` | `(name)` | Read env variable (Windows) |
| `cwd` | `()` | Current working directory (Linux/macOS) |
| `cwd_win` | `()` | Current working directory (Windows) |

### Data Loading

| Macro | Signature | Description |
|-------|-----------|-------------|
| `load_csv_url` | `(url)` | Load CSV from URL as TABLE |
| `load_json_url` | `(url)` | Load JSON from URL as TABLE |
| `load_parquet_url` | `(url)` | Load Parquet from URL as TABLE |

### Power Macros (LLM + Tools)

| Macro | Signature | Description |
|-------|-----------|-------------|
| `search_and_summarize` | `(query)` | DuckDuckGo search + DeepSeek summary |
| `analyze_page` | `(url, question)` | Fetch page + DeepSeek analysis |
| `review_code` | `(file_path)` | Read file + DeepSeek code review |
| `explain_code` | `(file_path)` | Read file + DeepSeek explanation |
| `generate_py` | `(task)` | Generate Python code with DeepSeek |
| `elevenlabs_tts` | `(text_input)` | ElevenLabs text-to-speech (TABLE) |

---

## agent.sql — Security & Approval (23)

### Path & Domain Policy

| Macro | Signature | Description |
|-------|-----------|-------------|
| `path_in_workspace` | `(check_path, workspace_path)` | Check if path is under workspace root |
| `is_allowed_path` | `(agent_id, check_path)` | Check path against `workspaces` table |
| `get_workspace_mode` | `(agent_id, check_path)` | Get workspace mode (`reader`/`writer`/`operator`) |
| `is_allowed_domain` | `(agent_id, domain)` | Check domain against allow/block lists |

### Security Policy

| Macro | Signature | Description |
|-------|-----------|-------------|
| `is_shell_enabled` | `(agent_id)` | Whether shell is enabled for agent |
| `is_blocked_command` | `(agent_id, cmd)` | Check command against blocklist |
| `is_sensitive_file` | `(agent_id, file_path)` | Check file against sensitive patterns |
| `can_write_to_workspace` | `(agent_id, file_path)` | Whether agent can write to path |

### Secure Operations

| Macro | Signature | Description |
|-------|-----------|-------------|
| `secure_read` | `(agent_id, file_path)` | Policy-gated file read |
| `secure_write` | `(agent_id, file_path, content)` | Policy-gated file write |
| `secure_ls` | `(agent_id, dir_path)` | Policy-gated directory list |
| `secure_shell` | `(agent_id, cmd)` | Policy-gated shell execution |
| `safe_read_content` | `(agent_id, file_path)` | Read with injection detection |

### Audit Logging

| Macro | Signature | Description |
|-------|-----------|-------------|
| `log_tool_call` | `(session_id, tool_name, params, result, decision)` | Log tool call to audit |
| `log_violation` | `(session_id, tool_name, violations)` | Log policy violation |
| `recent_audit` | `(session_id, limit_n)` | Last N audit entries for session (TABLE) |

### Agent Config

| Macro | Signature | Description |
|-------|-----------|-------------|
| `create_agent` | `(id, name, role, sec_profile)` | Create agent config descriptor |
| `add_workspace` | `(ws_id, agent_id, path, name, mode)` | Add workspace descriptor |
| `init_security_policy` | `(agent_id, shell_on, allowlist, blocklist)` | Init security policy descriptor |
| `get_agent_config` | `(agent_id)` | Full agent config as JSON |

### Approval & Injection

| Macro | Signature | Description |
|-------|-----------|-------------|
| `requires_approval` | `(agent_id, tool_name, tool_params)` | Whether tool call needs approval |
| `request_approval` | `(session_id, tool_name, params, reason)` | Create persistent approval request |
| `detect_injection` | `(content)` | Detect prompt injection patterns, returns type or NULL |

---

## harness.sql — Agent Harness & Routing (13)

### Anthropic API

| Macro | Signature | Description |
|-------|-----------|-------------|
| `anthropic_base` | `()` | Anthropic base URL (`ANTHROPIC_BASE_URL` or default) |
| `anthropic_chat` | `(model, messages_json, max_tokens)` | Anthropic Messages API call |
| `anthropic_chat_tools` | `(model, messages_json, tools_json, max_tokens)` | Anthropic with tool-calling |

### Model Routing

| Macro | Signature | Description |
|-------|-----------|-------------|
| `model_call` | `(agent_id, user_prompt, tools_json)` | Route to Ollama or Anthropic based on `model_backend` |
| `agent_system_prompt` | `(agent_id)` | Build system prompt from agent config |
| `secure_agent_call` | `(agent_id, model, user_prompt, tools_json)` | Agent call with system prompt |

### Tool Schemas

| Macro | Signature | Description |
|-------|-----------|-------------|
| `local_tools_schema` | `()` | Basic tool schema (fs_read, fs_list, shell_run, web_search) |
| `agent_tools_schema` | `()` | Full tool schema including fs_write and task_complete |

### Tool Execution

| Macro | Signature | Description |
|-------|-----------|-------------|
| `execute_tool` | `(agent_id, session_id, tool_name, params)` | Execute tool without approval check |
| `execute_tool_safe` | `(agent_id, session_id, tool_name, params)` | Execute tool with approval gate |
| `process_tool_call` | `(agent_id, session_id, tool_call_json)` | Process single tool call from LLM response |

### Agent Loop

| Macro | Signature | Description |
|-------|-----------|-------------|
| `agent_step` | `(agent_id, session_id, messages_json)` | One step of the agent loop (model → tools → result) |
| `quick_agent` | `(agent_id, user_prompt)` | One-shot agent call with auto system prompt |

---

## orgs.sql — Organizations & Orchestration (16)

### Org Helpers

| Macro | Signature | Description |
|-------|-----------|-------------|
| `get_org_prompt` | `(org_id)` | Get org system prompt |
| `get_org_model` | `(org_id)` | Get org primary model |
| `is_org_tool_allowed` | `(org_id, tool_name)` | Check if tool is enabled for org |
| `org_tool_requires_approval` | `(org_id, tool_name)` | Whether tool needs approval in org |
| `is_org_action_denied` | `(org_id, denial_type, pattern)` | Check against org denial rules |
| `get_denial_reason` | `(org_id, denial_type, pattern)` | Get denial reason text |
| `org_can_execute` | `(org_id, tool_name, params)` | Full policy check (allowed + approval needed) |

### Orchestrator Routing

| Macro | Signature | Description |
|-------|-----------|-------------|
| `log_org_call` | `(session_id, caller, target, task)` | Log inter-org call |
| `complete_org_call` | `(call_id, result_json)` | Mark org call as complete |
| `call_org` | `(caller_id, target_id, session_id, task)` | Dispatch task to another org |
| `orchestrator_tools_schema` | `()` | Tool schema for OrchestratorOrg |
| `execute_orchestrator_tool` | `(session_id, tool_name, params)` | Execute orchestrator routing tool |

### Org-Specific Tool Schemas

| Macro | Signature | Description |
|-------|-----------|-------------|
| `dev_org_tools_schema` | `()` | DevOrg: fs_read/write, git, test_run |
| `ops_org_tools_schema` | `()` | OpsOrg: ci_trigger, deploy, rollback, render |
| `research_org_tools_schema` | `()` | ResearchOrg: searxng_search, notes |
| `studio_org_tools_schema` | `()` | StudioOrg: fs, notes_board |

---

## org_tools.sql — Org Operations (25)

Search, CI/CD, notes, render jobs, and approval-gated deployments.

| Group | Macros |
|-------|--------|
| **SearXNG Search** | `searxng_endpoint`, `searxng`, `searxng_news`, `searxng_it`, `searxng_science` |
| **CI/CD** | `ci_trigger`, `ci_status`, `pipeline_logs` |
| **Deploy / Rollback** | `deploy_service`, `rollback_service` (both require approval) |
| **Render Jobs** | `render_job_submit`, `render_job_status`, `render_job_cancel`, `render_job_list` |
| **Notes Board** | `notes_board_create`, `notes_board_list`, `notes_board_get`, `notes_board_update`, `notes_board_delete` |
| **Research Notes** | `research_note_save`, `research_note_list`, `research_note_get` |
| **Helpers** | `request_tool_approval`, `open_approval_ui` |

---

## ui.sql — MCP Apps & UI (35)

MiniJinja-rendered HTML/JSON UI templates exposed via MCP.

| Group | Macros |
|-------|--------|
| **App Registry** | `register_app`, `get_app`, `list_apps`, `render_app` |
| **Approval UI** | `render_approval_list`, `render_approval_detail`, `resolve_approval`, `request_tool_approval` |
| **Spec Viewer** | `render_spec_list`, `render_spec_detail`, `render_spec_editor` |
| **Org Dashboard** | `render_org_dashboard`, `render_org_tools`, `render_org_calls` |
| **Agent Monitor** | `render_agent_sessions`, `render_session_detail`, `render_audit_log` |
| **Radio Monitor** | `render_radio_channels`, `render_radio_messages` |
| **Search UI** | `render_search_results`, `render_search_form` |
| **Status** | `render_status_page`, `render_extension_list` |
| **Notes** | `render_notes_board`, `render_note_editor` |
| **Render Jobs** | `render_job_list_ui`, `render_job_detail` |

---

## extensions.sql — Advanced Extensions (33)

JSONata, Radio pub/sub, DuckPGQ graph queries, Bitfilter hybrid scoring, Lindel sequence ops.

| Group | Macros |
|-------|--------|
| **JSONata** | `jsonata_eval`, `jsonata_transform`, `jsonata_extract` |
| **Radio (persistent pub/sub)** | `radio_publish`, `radio_subscribe`, `radio_unsubscribe`, `radio_receive`, `radio_pending`, `radio_channels` |
| **DuckPGQ (graph)** | `graph_create`, `graph_shortest_path`, `graph_neighbors`, `graph_pagerank` |
| **Bitfilter (hybrid ranking)** | `bitfilter_create`, `bitfilter_score`, `hybrid_rank`, `semantic_keyword_hybrid` |
| **Lindel (sequence ops)** | `levenshtein_score`, `lindel_align`, `lindel_diff`, `edit_distance_norm` |
| **Misc** | `getenv`, `format_json`, `json_pretty`, `merge_json` |

---

## spec/ — Spec Engine (55)

### spec/macros.sql — Spec CRUD & Rendering (39)

| Group | Macros |
|-------|--------|
| **Spec Queries** | `spec_get`, `spec_list_active`, `spec_list_by_kind`, `spec_search`, `spec_stats`, `spec_by_name`, `spec_count` |
| **Spec Mutations** | `spec_create_sql`, `spec_update_sql`, `spec_activate`, `spec_deactivate`, `spec_delete_sql` |
| **Template Rendering** | `spec_render_template`, `spec_render_template_v`, `spec_render`, `spec_render_direct_udf`, `spec_render_template_udf`, `spec_render_template_version_udf` |
| **Relationships** | `spec_add_relationship`, `spec_get_relationships`, `spec_get_deps`, `spec_get_dependents` |
| **MCP Registry** | `mcp_list`, `mcp_list_tools`, `mcp_list_prompts`, `mcp_list_resources`, `mcp_list_remote`, `mcp_list_tools_remote`, `mcp_list_prompts_remote` |
| **Agent Specs** | `spec_get_agent`, `spec_get_skill`, `spec_get_api`, `spec_get_schema`, `spec_get_template` |
| **Learning** | `spec_record_feedback`, `spec_record_adaptation`, `spec_get_learnings` |
| **Intelligence** | `spec_intelligence_summary`, `spec_hot_specs`, `spec_quality_report` |

### spec/rag.sql — RAG & Vector Search (16)

| Macro | Signature | Description |
|-------|-----------|-------------|
| `store_embedding` | `(spec_id, content, content_type, embedding)` | Store vector embedding |
| `vss_search_embeddings` | `(query_vec, limit_count)` | Vector similarity search |
| `vss_search_all` | `(query_text, limit_count)` | VSS with auto-embedding |
| `vss_search_code` | `(query_text, limit_count)` | VSS filtered to code specs |
| `vss_search_research` | `(query_text, limit_count)` | VSS filtered to research |
| `vss_search_decisions` | `(query_text, limit_count)` | VSS filtered to decisions |
| `vss_search_memory` | `(query_text, limit_count)` | VSS filtered to memories |
| `hybrid_search_embeddings` | `(query_text, query_vec, limit_count)` | Keyword + vector hybrid search |
| `hybrid_search_all` | `(query_text, limit_count)` | Hybrid search with auto-embedding |
| `build_rag_context` | `(query_text, limit_count)` | Build ranked context string for RAG |
| `rag_relevant_specs` | `(query_text, limit_count)` | Get most relevant specs as context |
| `get_conversation_context` | `(query_text, limit_count)` | Get relevant conversation memories |
| `find_similar_conversations` | `(query_text, limit_count)` | Find similar past conversations |
| `store_conversation_memory` | `(session_id, role, content, embedding)` | Store conversation turn with embedding |
| `store_org_knowledge` | `(org_id, title, content, knowledge_type, embedding)` | Store org knowledge entry |
| `search_similar` | `(query_vec, limit_count)` | Direct vector search on spec_embeddings |

---

## Usage Examples

```sql
-- LLM
SELECT deepseek('What is DuckDB?');
SELECT kimi_think('Design a distributed caching system');

-- Web
SELECT ddg_abstract('agent-farm duckdb');
SELECT searxng('python async patterns');

-- Files & Git
SELECT read_file('README.md');
SELECT git_log(10);
SELECT review_code('src/agent_farm/main.py');

-- Secure agent tools
SELECT secure_read('dev-agent', '/projects/dev/main.py');
SELECT quick_agent('dev-agent', 'Summarize the project structure');

-- Spec Engine
SELECT * FROM spec_list_by_kind('agent');
SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');
SELECT * FROM hybrid_search_all('authentication flow', 5);

-- Radio pub/sub
SELECT radio_publish('alerts', '{"msg": "deploy started"}');
SELECT * FROM radio_receive('alerts');

-- Approval workflow
SELECT request_approval('session-1', 'fs_delete', '{"path": "/tmp/test"}', 'Cleanup task');
-- Then via CLI: agent-farm approval list / agent-farm approval resolve 1 approved
```
