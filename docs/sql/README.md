# SQL Macros by File

One **MD file per SQL file**. Source of truth is always the corresponding `.sql` under `src/agent_farm/sql/`.

## Overview (for humans)

| Category | SQL file | Contents |
|----------|----------|----------|
| **Core** | [base](base.md) | Secrets, URL-encode, timestamps |
| **LLM** | [ollama](ollama.md) | Ollama chat, embeddings, model shortcuts |
| **LLM** | [harness](harness.md) | Anthropic, agent calls, tool schema |
| **Tools** | [tools](tools.md) | Web, shell, Python, fetch, files, Git |
| **Tools** | [agent](agent.md) | Security, workspace, approval, audit |
| **Org** | [orgs](orgs.md) | Org prompts, permissions, call_org |
| **Org** | [org_tools](org_tools.md) | SearXNG, CI, deploy, render, notes, tests |
| **Ext** | [extensions](extensions.md) | JSONata, orchestrator, ops/research/studio macros |
| **UI** | [ui](ui.md) | MCP apps, templates, approval UI, profile |
| **Spec** | [spec_macros](spec_macros.md) | Spec Engine: queries, render, validation, MCP remote |
| **Spec** | [spec_rag](spec_rag.md) | VSS/hybrid search, RAG context, memory |
| **Spec** | [spec_schema](spec_schema.md) | Tables & views (no macros) |
| **Spec** | [spec_intelligence](spec_intelligence.md) | Embedding, knowledge, memory tables |
| **Spec** | [spec_http](spec_http.md) | HTTP server configuration |
| **Spec** | [spec_seed](spec_seed.md) | Seed data (spec objects) |

## Finding macros (for AIs)

- **Spec queries** (spec_list, spec_get, spec_search, …) → [spec_macros](spec_macros.md)
- **LLM / chat / embed** → [ollama](ollama.md) or [harness](harness.md)
- **Web, shell, Python, Git, files** → [tools](tools.md)
- **Security, approval, audit** → [agent](agent.md)
- **Org config, call_org** → [orgs](orgs.md)
- **SearXNG, CI, deploy, notes** → [org_tools](org_tools.md)
- **RAG, VSS, hybrid search** → [spec_rag](spec_rag.md)
- **MCP apps, UI templates** → [ui](ui.md)

Load order of SQL files: see `main.SQL_LOAD_ORDER` and `src/agent_farm/sql/`.
