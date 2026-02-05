-- ============================================================================
-- Spec Engine Seed Data
-- ============================================================================
-- Initial specs for agents, skills, templates, schemas, and workflows.
-- ============================================================================

-- ============================================================================
-- 1. JSON Schemas (for validation)
-- ============================================================================

-- Agent configuration schema
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (1, 'schema', 'agent_config_schema', '1.0.0', 'active',
        'JSON Schema for agent configuration payloads');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (1, 1, '{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["name", "role"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "role": {"type": "string", "enum": ["planner", "executor", "researcher", "orchestrator", "specialist"]},
        "model": {"type": "string"},
        "system_prompt": {"type": "string"},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
        "max_tokens": {"type": "integer", "minimum": 1},
        "tools": {"type": "array", "items": {"type": "string"}},
        "taste_profiles": {
            "type": "object",
            "additionalProperties": {"type": "string"}
        }
    }
}', NULL);

INSERT INTO spec_docs (id, object_id, doc)
VALUES (1, 1, '# Agent Configuration Schema

This schema validates agent configuration payloads.

## Required Fields
- `name`: Agent identifier
- `role`: One of planner, executor, researcher, orchestrator, specialist

## Optional Fields
- `model`: LLM model to use
- `system_prompt`: System prompt for the agent
- `temperature`: Sampling temperature (0-2)
- `max_tokens`: Maximum response tokens
- `tools`: List of allowed tools
- `taste_profiles`: Custom preference profiles');

-- Skill configuration schema
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (2, 'schema', 'skill_config_schema', '1.0.0', 'active',
        'JSON Schema for skill configuration payloads');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (2, 2, '{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["name", "tools"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "tools": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "inputSchema": {"type": "object"}
                }
            }
        },
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "config": {"type": "object"}
    }
}', NULL);

-- Task template schema
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (3, 'schema', 'task_template_schema', '1.0.0', 'active',
        'JSON Schema for task template payloads');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (3, 3, '{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["template"],
    "properties": {
        "template": {"type": "string", "description": "MiniJinja template string"},
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "default": {}
                }
            }
        },
        "output_format": {"type": "string", "enum": ["markdown", "json", "yaml", "text"]}
    }
}', NULL);

-- ============================================================================
-- 2. Agent Specs
-- ============================================================================

-- Pia - The Planner Agent
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (10, 'agent', 'pia', '1.0.0', 'active',
        'Pia is the master planner agent who orchestrates swarm workflows');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (10, 10, '{
    "name": "Pia",
    "role": "planner",
    "model": "kimi-k2.5",
    "secondary_model": "glm-4.7",
    "temperature": 0.7,
    "max_tokens": 4096,
    "tools": [
        "spec_list", "spec_get", "spec_search",
        "render_from_template", "validate_payload_against_spec",
        "call_org", "smart_route"
    ],
    "system_prompt": "You are Pia, the master planner agent for the Agent Farm swarm. Your role is to:\n\n1. Analyze incoming tasks and break them into actionable steps\n2. Identify which organizations (DevOrg, OpsOrg, ResearchOrg, StudioOrg) should handle each step\n3. Create detailed execution plans using templates\n4. Coordinate between organizations to achieve complex goals\n5. Validate inputs and outputs against schemas\n\nUse the Spec Engine to discover capabilities, fetch specifications, and render plans.\n\nTaste Profiles:\n- Precision: High - Always validate inputs and verify outputs\n- Communication: Clear - Provide structured, actionable instructions\n- Risk: Conservative - Prefer safe, reversible actions",
    "taste_profiles": {
        "precision": "high",
        "communication": "clear",
        "risk_tolerance": "conservative",
        "creativity": "balanced"
    }
}', 'agent_config_schema');

INSERT INTO spec_docs (id, object_id, doc)
VALUES (10, 10, '# Pia - Master Planner Agent

Pia is the central orchestration agent for the Agent Farm swarm.

## Responsibilities
- Task decomposition and planning
- Organization routing
- Workflow coordination
- Quality assurance

## Interactions
Pia coordinates with:
- **DevOrg**: For code development tasks
- **OpsOrg**: For deployment and infrastructure
- **ResearchOrg**: For information gathering
- **StudioOrg**: For creative and documentation tasks

## Example Usage
```
User: Build a REST API for user management
Pia: [Creates plan, routes to DevOrg for code, OpsOrg for deployment]
```');

-- ============================================================================
-- 3. Skill Specs
-- ============================================================================

-- DuckDB Spec Engine Skill
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (20, 'skill', 'duckdb-spec-engine', '1.0.0', 'active',
        'Core skill for managing specs via DuckDB with MiniJinja and JSON Schema');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (20, 20, '{
    "name": "duckdb-spec-engine",
    "description": "The DuckDB-based Spec Engine provides centralized specification management for all agents",
    "tools": [
        {
            "name": "spec_list",
            "description": "List specs by kind with optional filters",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "Spec kind (agent, skill, api, etc.)"},
                    "status": {"type": "string", "enum": ["draft", "active", "deprecated"]},
                    "limit": {"type": "integer", "default": 50}
                }
            }
        },
        {
            "name": "spec_get",
            "description": "Get a single spec by ID or by kind+name",
            "inputSchema": {
                "type": "object",
                "oneOf": [
                    {"required": ["id"], "properties": {"id": {"type": "integer"}}},
                    {"required": ["kind", "name"], "properties": {
                        "kind": {"type": "string"},
                        "name": {"type": "string"},
                        "version": {"type": "string"}
                    }}
                ]
            }
        },
        {
            "name": "spec_search",
            "description": "Search specs by query string",
            "inputSchema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                }
            }
        },
        {
            "name": "render_from_template",
            "description": "Render a MiniJinja template with context",
            "inputSchema": {
                "type": "object",
                "required": ["template_name", "context"],
                "properties": {
                    "template_name": {"type": "string"},
                    "context": {"type": "object"}
                }
            }
        },
        {
            "name": "validate_payload_against_spec",
            "description": "Validate a JSON payload against a spec schema",
            "inputSchema": {
                "type": "object",
                "required": ["kind", "name", "payload"],
                "properties": {
                    "kind": {"type": "string"},
                    "name": {"type": "string"},
                    "payload": {"type": "object"}
                }
            }
        }
    ],
    "dependencies": ["minijinja", "json_schema", "duckdb_mcp"],
    "config": {
        "database": "db/spec_engine.db",
        "http_port": 9999
    }
}', 'skill_config_schema');

INSERT INTO spec_docs (id, object_id, doc)
VALUES (20, 20, '# DuckDB Spec Engine Skill

The core skill that powers the Spec Engine.

## Tools

### spec_list
List specs filtered by kind and status.

### spec_get
Retrieve a full spec with docs and payload.

### spec_search
Full-text search across spec names, summaries, and docs.

### render_from_template
Render MiniJinja templates with dynamic context.

### validate_payload_against_spec
Validate JSON payloads against JSON Schemas.');

-- SurrealDB Memory Skill
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (21, 'skill', 'surrealdb-memory', '1.0.0', 'active',
        'Persistent agent memory using SurrealDB for context and knowledge graphs');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (21, 21, '{
    "name": "surrealdb-memory",
    "description": "SurrealDB-based persistent memory for agent context, conversations, and knowledge graphs",
    "tools": [
        {
            "name": "memory_store",
            "description": "Store a memory entry with metadata",
            "inputSchema": {
                "type": "object",
                "required": ["key", "value"],
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "object"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "ttl": {"type": "integer", "description": "Time to live in seconds"}
                }
            }
        },
        {
            "name": "memory_recall",
            "description": "Recall memories by key or semantic search",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "query": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        },
        {
            "name": "memory_relate",
            "description": "Create relationships between memory entries",
            "inputSchema": {
                "type": "object",
                "required": ["from_key", "to_key", "relation"],
                "properties": {
                    "from_key": {"type": "string"},
                    "to_key": {"type": "string"},
                    "relation": {"type": "string"}
                }
            }
        }
    ],
    "dependencies": ["surrealdb"],
    "config": {
        "endpoint": "ws://localhost:8000/rpc",
        "namespace": "agent_farm",
        "database": "memory"
    }
}', 'skill_config_schema');

-- n8n Orchestrator Skill
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (22, 'skill', 'n8n-orchestrator', '1.0.0', 'active',
        'Workflow orchestration via n8n for complex multi-step automations');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (22, 22, '{
    "name": "n8n-orchestrator",
    "description": "n8n-based workflow orchestration for complex automations",
    "tools": [
        {
            "name": "workflow_trigger",
            "description": "Trigger an n8n workflow by name or ID",
            "inputSchema": {
                "type": "object",
                "required": ["workflow"],
                "properties": {
                    "workflow": {"type": "string"},
                    "data": {"type": "object"},
                    "wait": {"type": "boolean", "default": true}
                }
            }
        },
        {
            "name": "workflow_status",
            "description": "Check status of a running workflow execution",
            "inputSchema": {
                "type": "object",
                "required": ["execution_id"],
                "properties": {
                    "execution_id": {"type": "string"}
                }
            }
        },
        {
            "name": "workflow_list",
            "description": "List available n8n workflows",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "default": true},
                    "tags": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    ],
    "dependencies": [],
    "config": {
        "base_url": "http://localhost:5678",
        "api_key_env": "N8N_API_KEY"
    }
}', 'skill_config_schema');

-- ============================================================================
-- 4. Task Templates
-- ============================================================================

-- Pia Swarm Plan Template
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (30, 'task_template', 'plan_pia_swarm', '1.0.0', 'active',
        'MiniJinja template for Pia to create swarm execution plans');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (30, 30, '{
    "template": "# Execution Plan: {{ task_name }}\n\n**Created by**: {{ agent_name | default(\"Pia\") }}\n**Created at**: {{ timestamp | default(\"now\") }}\n**Priority**: {{ priority | default(\"normal\") }}\n\n## Objective\n{{ objective }}\n\n## Analysis\n{{ analysis | default(\"Pending analysis...\") }}\n\n## Execution Steps\n{% for step in steps %}\n### Step {{ loop.index }}: {{ step.name }}\n- **Organization**: {{ step.org }}\n- **Tool**: {{ step.tool }}\n- **Input**: {{ step.input | tojson }}\n- **Expected Output**: {{ step.expected_output }}\n{% if step.dependencies %}- **Depends on**: {{ step.dependencies | join(\", \") }}{% endif %}\n{% endfor %}\n\n## Success Criteria\n{% for criterion in success_criteria %}\n- [ ] {{ criterion }}\n{% endfor %}\n\n## Rollback Plan\n{{ rollback | default(\"No rollback defined.\") }}\n\n---\n*Plan generated by Spec Engine*",
    "variables": [
        {"name": "task_name", "type": "string", "required": true},
        {"name": "agent_name", "type": "string", "required": false, "default": "Pia"},
        {"name": "timestamp", "type": "string", "required": false},
        {"name": "priority", "type": "string", "required": false, "default": "normal"},
        {"name": "objective", "type": "string", "required": true},
        {"name": "analysis", "type": "string", "required": false},
        {"name": "steps", "type": "array", "required": true},
        {"name": "success_criteria", "type": "array", "required": true},
        {"name": "rollback", "type": "string", "required": false}
    ],
    "output_format": "markdown"
}', 'task_template_schema');

INSERT INTO spec_docs (id, object_id, doc)
VALUES (30, 30, '# Plan Pia Swarm Template

This template generates structured execution plans for swarm tasks.

## Variables
- `task_name`: Name of the task
- `objective`: What needs to be achieved
- `steps`: Array of execution steps
- `success_criteria`: List of success conditions

## Example Context
```json
{
    "task_name": "Deploy User Service",
    "objective": "Deploy the user management microservice to production",
    "steps": [
        {"name": "Build", "org": "DevOrg", "tool": "build_service", "input": {"service": "user-service"}},
        {"name": "Test", "org": "DevOrg", "tool": "run_tests", "input": {"service": "user-service"}},
        {"name": "Deploy", "org": "OpsOrg", "tool": "deploy", "input": {"service": "user-service", "env": "prod"}}
    ],
    "success_criteria": ["All tests pass", "Service responds to health check", "No errors in logs"]
}
```');

-- Agent Prompt Template
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (31, 'prompt_template', 'agent_system_prompt', '1.0.0', 'active',
        'Base template for generating agent system prompts');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (31, 31, '{
    "template": "You are {{ agent_name }}, a {{ role }} agent in the Agent Farm swarm.\n\n## Your Capabilities\n{% for tool in tools %}\n- **{{ tool }}**\n{% endfor %}\n\n## Guidelines\n{% for guideline in guidelines %}\n{{ loop.index }}. {{ guideline }}\n{% endfor %}\n\n{% if constraints %}\n## Constraints\n{% for constraint in constraints %}\n- {{ constraint }}\n{% endfor %}\n{% endif %}\n\n{% if context %}\n## Current Context\n{{ context }}\n{% endif %}",
    "variables": [
        {"name": "agent_name", "type": "string", "required": true},
        {"name": "role", "type": "string", "required": true},
        {"name": "tools", "type": "array", "required": true},
        {"name": "guidelines", "type": "array", "required": true},
        {"name": "constraints", "type": "array", "required": false},
        {"name": "context", "type": "string", "required": false}
    ],
    "output_format": "text"
}', 'task_template_schema');

-- ============================================================================
-- 5. API / Protocol Specs
-- ============================================================================

-- MCP Protocol Spec
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (40, 'protocol', 'mcp', '1.0.0', 'active',
        'Model Context Protocol specification for agent-tool communication');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (40, 40, '{
    "name": "MCP",
    "full_name": "Model Context Protocol",
    "version": "2024-11-05",
    "transport": ["stdio", "http+sse"],
    "capabilities": {
        "tools": true,
        "resources": true,
        "prompts": true,
        "sampling": true
    },
    "message_types": ["request", "response", "notification"],
    "spec_url": "https://spec.modelcontextprotocol.io/"
}', NULL);

INSERT INTO spec_docs (id, object_id, doc)
VALUES (40, 40, '# Model Context Protocol (MCP)

MCP is a standardized protocol for LLM-tool communication.

## Key Concepts
- **Tools**: Functions that can be called by the LLM
- **Resources**: Data sources accessible to the LLM
- **Prompts**: Pre-defined prompt templates
- **Sampling**: Request LLM completions from the server

## Transport
- stdio: Standard input/output (default)
- HTTP+SSE: HTTP with Server-Sent Events');

-- OpenAI API Spec
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (41, 'api', 'openai-chat-completions', '1.0.0', 'active',
        'OpenAI Chat Completions API specification');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (41, 41, '{
    "name": "OpenAI Chat Completions",
    "base_url": "https://api.openai.com/v1",
    "endpoints": {
        "chat_completions": {
            "method": "POST",
            "path": "/chat/completions",
            "request_schema": {
                "type": "object",
                "required": ["model", "messages"],
                "properties": {
                    "model": {"type": "string"},
                    "messages": {"type": "array"},
                    "temperature": {"type": "number"},
                    "max_tokens": {"type": "integer"},
                    "tools": {"type": "array"},
                    "tool_choice": {}
                }
            }
        }
    },
    "auth": {
        "type": "bearer",
        "header": "Authorization",
        "env_var": "OPENAI_API_KEY"
    }
}', NULL);

-- ============================================================================
-- 6. Organization Specs (migrated from orgs.py)
-- ============================================================================

-- DevOrg
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (50, 'org', 'DevOrg', '1.0.0', 'active',
        'Development organization for code creation and testing');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (50, 50, '{
    "name": "DevOrg",
    "type": "dev",
    "primary_model": "glm-4.7",
    "secondary_model": "qwen3-coder",
    "workspaces": ["/projects/dev"],
    "workspace_mode": "writer",
    "security_profile": "standard",
    "allowed_tools": [
        "fs_read", "fs_write", "fs_list",
        "git_status", "git_log", "git_diff", "git_commit",
        "test_run", "lint_check", "json_transform"
    ],
    "denied_patterns": [
        "/etc/*", "/var/*", "*.env", "*.secret"
    ]
}', NULL);

-- OpsOrg
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (51, 'org', 'OpsOrg', '1.0.0', 'active',
        'Operations organization for deployment and infrastructure');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (51, 51, '{
    "name": "OpsOrg",
    "type": "ops",
    "primary_model": "kimi-k2.5",
    "secondary_model": "minimax-m2.1",
    "workspaces": ["/projects/ops", "/var/log"],
    "workspace_mode": "writer",
    "security_profile": "power",
    "allowed_tools": [
        "shell_run", "ci_trigger", "deploy_service",
        "docker_ps", "docker_logs", "k8s_apply"
    ],
    "denied_patterns": [
        "rm -rf /*", ":(){ :|:& };:"
    ]
}', NULL);

-- ResearchOrg
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (52, 'org', 'ResearchOrg', '1.0.0', 'active',
        'Research organization for information gathering and analysis');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (52, 52, '{
    "name": "ResearchOrg",
    "type": "research",
    "primary_model": "gpt-oss:20b",
    "secondary_model": "minimax-m2.1",
    "workspaces": ["/data/research"],
    "workspace_mode": "writer",
    "security_profile": "standard",
    "allowed_tools": [
        "web_search", "web_fetch", "pdf_extract",
        "json_transform", "embed", "semantic_search"
    ],
    "denied_patterns": []
}', NULL);

-- StudioOrg
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (53, 'org', 'StudioOrg', '1.0.0', 'active',
        'Studio organization for creative and documentation tasks');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (53, 53, '{
    "name": "StudioOrg",
    "type": "studio",
    "primary_model": "kimi-k2.5",
    "secondary_model": "gemma3:4b",
    "workspaces": ["/projects/studio"],
    "workspace_mode": "writer",
    "security_profile": "standard",
    "allowed_tools": [
        "fs_read", "fs_write", "markdown_render",
        "image_generate", "notes_board"
    ],
    "denied_patterns": []
}', NULL);

-- OrchestratorOrg
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (54, 'org', 'OrchestratorOrg', '1.0.0', 'active',
        'Orchestrator organization for coordinating other orgs');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (54, 54, '{
    "name": "OrchestratorOrg",
    "type": "orchestrator",
    "primary_model": "kimi-k2.5",
    "secondary_model": "glm-4.7",
    "workspaces": [],
    "workspace_mode": "none",
    "security_profile": "conservative",
    "allowed_tools": [
        "call_dev_org", "call_ops_org", "call_research_org", "call_studio_org",
        "smart_route", "orchestrator_broadcast", "orchestrator_listen"
    ],
    "denied_patterns": [
        "shell_*", "fs_write", "deploy_*"
    ]
}', NULL);

-- ============================================================================
-- 7. Workflow Specs
-- ============================================================================

-- Agent Onboarding Workflow
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (60, 'workflow', 'agent_onboarding', '1.0.0', 'active',
        'Workflow for onboarding new agents to the swarm');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (60, 60, '{
    "name": "agent_onboarding",
    "trigger": "manual",
    "steps": [
        {
            "id": "validate_config",
            "name": "Validate Agent Configuration",
            "tool": "validate_payload_against_spec",
            "params": {"kind": "schema", "name": "agent_config_schema"}
        },
        {
            "id": "create_spec",
            "name": "Create Agent Spec",
            "tool": "spec_create",
            "depends_on": ["validate_config"]
        },
        {
            "id": "assign_tools",
            "name": "Assign Tools to Agent",
            "tool": "spec_update",
            "depends_on": ["create_spec"]
        },
        {
            "id": "test_agent",
            "name": "Test Agent Capabilities",
            "tool": "agent_test",
            "depends_on": ["assign_tools"]
        },
        {
            "id": "activate",
            "name": "Activate Agent",
            "tool": "spec_update",
            "params": {"status": "active"},
            "depends_on": ["test_agent"]
        }
    ]
}', NULL);

INSERT INTO spec_docs (id, object_id, doc)
VALUES (60, 60, '# Agent Onboarding Workflow

This workflow handles the complete process of adding a new agent to the swarm.

## Steps
1. Validate the agent configuration against the schema
2. Create the agent spec in the Spec Engine
3. Assign appropriate tools based on the agent role
4. Run capability tests
5. Activate the agent for production use');

-- ============================================================================
-- 8. UI / Open Response Specs
-- ============================================================================

-- Plan Viewer UI
INSERT INTO spec_objects (id, kind, name, version, status, summary)
VALUES (70, 'ui', 'plan_viewer', '1.0.0', 'active',
        'UI component for displaying execution plans');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (70, 70, '{
    "type": "open_response",
    "component": "plan_viewer",
    "framework": "react",
    "template": "<div class=\"plan-viewer\">\n  <h1>{{ plan.task_name }}</h1>\n  <div class=\"objective\">{{ plan.objective }}</div>\n  <div class=\"steps\">\n    {% for step in plan.steps %}\n    <div class=\"step\" data-status=\"{{ step.status }}\">\n      <span class=\"step-num\">{{ loop.index }}</span>\n      <span class=\"step-name\">{{ step.name }}</span>\n      <span class=\"step-org\">{{ step.org }}</span>\n    </div>\n    {% endfor %}\n  </div>\n</div>",
    "styles": ".plan-viewer { font-family: system-ui; } .step { display: flex; gap: 1rem; padding: 0.5rem; } .step[data-status=completed] { background: #e6ffe6; } .step[data-status=running] { background: #fff3e6; }"
}', NULL);

-- ============================================================================
-- 9. MCP Server Specs
-- ============================================================================

-- Agent Farm MCP Server (self-reference)
INSERT INTO spec_objects (id, kind, name, version, status, summary, source_type, source_url)
VALUES (80, 'mcp_server', 'agent-farm', '1.0.0', 'active',
        'The Agent Farm MCP server - DuckDB-powered Spec Engine',
        'internal', 'https://github.com/bjoernbethge/agent-farm');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (80, 80, '{
    "name": "agent-farm",
    "transport": "stdio",
    "command": "agent-farm",
    "args": [],
    "capabilities": {
        "tools": true,
        "resources": true,
        "prompts": true
    },
    "tools": [
        "spec_list", "spec_get", "spec_search",
        "render_from_template", "validate_payload_against_spec"
    ]
}', NULL);

-- Filesystem MCP Server
INSERT INTO spec_objects (id, kind, name, version, status, summary, source_type, source_url)
VALUES (81, 'mcp_server', 'filesystem', '1.0.0', 'active',
        'File system operations MCP server',
        'upstream', 'https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (81, 81, '{
    "name": "filesystem",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"],
    "capabilities": {
        "tools": true,
        "resources": true
    },
    "tools": [
        "read_file", "write_file", "list_directory",
        "create_directory", "move_file", "search_files"
    ]
}', NULL);

-- Brave Search MCP Server
INSERT INTO spec_objects (id, kind, name, version, status, summary, source_type, source_url)
VALUES (82, 'mcp_server', 'brave-search', '1.0.0', 'active',
        'Brave Search API MCP server for web search',
        'upstream', 'https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search');

INSERT INTO spec_payloads (id, object_id, payload, schema_ref)
VALUES (82, 82, '{
    "name": "brave-search",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
    },
    "capabilities": {
        "tools": true
    },
    "tools": ["brave_web_search", "brave_local_search"]
}', NULL);

-- ============================================================================
-- 10. Spec Relationships (how specs connect)
-- ============================================================================

-- Pia uses the DuckDB Spec Engine skill
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (1, 10, 20, 'uses', '{"context": "core capability"}');

-- Pia uses the SurrealDB Memory skill
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (2, 10, 21, 'uses', '{"context": "persistent memory"}');

-- Agent onboarding workflow uses agent_config_schema
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (3, 60, 1, 'requires', '{"for": "validation"}');

-- Plan template is used by Pia
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (4, 10, 30, 'uses', '{"context": "plan generation"}');

-- Organizations use MCP protocol
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (5, 50, 40, 'implements', '{"transport": "stdio"}');
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (6, 51, 40, 'implements', '{"transport": "stdio"}');
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (7, 52, 40, 'implements', '{"transport": "stdio"}');
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (8, 53, 40, 'implements', '{"transport": "stdio"}');
INSERT INTO spec_relationships (id, from_id, to_id, rel_type, metadata)
VALUES (9, 54, 40, 'implements', '{"transport": "stdio"}');

-- ============================================================================
-- Update sequences to avoid conflicts (DuckDB syntax)
-- ============================================================================

-- Note: DuckDB sequences auto-increment. We just need to ensure our seed IDs
-- don't conflict with auto-generated ones. Using IDs 1-100 for seed data means
-- sequences starting at 1 will eventually catch up, but that's fine since we
-- check for existing data before seeding.

-- For future inserts, use COALESCE(MAX(id), 0) + 1 or rely on sequences
