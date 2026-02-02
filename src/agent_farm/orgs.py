"""
Organization configurations for multi-agent system.

Defines 5 organizations with their models, tools, workspaces, and restrictions.
"""

from .schemas import OrgType, SecurityProfile, WorkspaceMode

# =============================================================================
# ORGANIZATION CONFIGURATIONS
# =============================================================================

ORG_CONFIGS = {
    # -------------------------------------------------------------------------
    # DevOrg - Development / Pipelines-as-Code
    # -------------------------------------------------------------------------
    OrgType.DEV: {
        "id": "dev-org",
        "name": "DevOrg",
        "description": "Development, code reviews, pipeline configurations",
        "model_primary": "glm-4.7:cloud",
        "model_secondary": "qwen3-coder:cloud",
        "security_profile": SecurityProfile.STANDARD,
        "workspaces": [
            {"path": "/projects/dev", "mode": WorkspaceMode.WRITER, "name": "Development"},
        ],
        "tools": [
            "fs_read",
            "fs_write",
            "fs_list",
            "git_status",
            "git_diff",
            "git_patch",
            "test_run",
            # Smart Extensions (JSONata)
            "json_transform",
            "dev_validate_config",
            "dev_extract_deps",
        ],
        "tools_requiring_approval": ["fs_write", "git_patch"],
        "denials": [
            ("shell", "*", "Shell access not allowed for DevOrg"),
            ("workspace", "/projects/ops/*", "No access to Ops workspace"),
            ("workspace", "/projects/studio/*", "No access to Studio workspace"),
            ("tool", "ci_trigger", "CI/CD triggers not allowed"),
            ("tool", "deploy_service", "Deployments not allowed"),
        ],
    },
    # -------------------------------------------------------------------------
    # OpsOrg - Operations / CI/CD & Render Execution
    # -------------------------------------------------------------------------
    OrgType.OPS: {
        "id": "ops-org",
        "name": "OpsOrg",
        "description": "CI/CD pipelines, deployments, render jobs",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "minimax-m2.1:cloud",
        "security_profile": SecurityProfile.POWER,
        "workspaces": [
            {"path": "/projects/ops", "mode": WorkspaceMode.WRITER, "name": "Operations"},
        ],
        "tools": [
            "fs_read",
            "fs_list",
            "ci_trigger",
            "deploy_service",
            "rollback_service",
            "render_job_submit",
            "render_job_status",
            "shell_run",
            # Smart Extensions (Bitfilters + Radio)
            "ops_is_duplicate",
            "ops_add_to_filter",
            "ops_subscribe_ci",
            "ops_publish_status",
        ],
        "tools_requiring_approval": [
            "deploy_service",
            "rollback_service",
            "shell_run",
        ],
        "shell_allowlist": [
            "kubectl",
            "docker",
            "systemctl status",
            "journalctl",
            "df",
            "free",
            "top -b -n 1",
        ],
        "denials": [
            ("workspace", "/projects/dev/*", "No write access to dev repos"),
            ("tool", "fs_write", "Code changes only via DevOrg"),
            ("tool", "git_patch", "Code changes only via DevOrg"),
        ],
    },
    # -------------------------------------------------------------------------
    # ResearchOrg - Research via SearXNG
    # -------------------------------------------------------------------------
    OrgType.RESEARCH: {
        "id": "research-org",
        "name": "ResearchOrg",
        "description": "External research, summaries, research notes",
        "model_primary": "gpt-oss:20b-cloud",
        "model_secondary": "minimax-m2.1:cloud",
        "security_profile": SecurityProfile.CONSERVATIVE,
        "workspaces": [
            {"path": "/data/research", "mode": WorkspaceMode.WRITER, "name": "Research Notes"},
        ],
        "tools": [
            "searxng_search",
            "fs_read",
            "fs_write_note",
            "fs_list_notes",
            # Smart Extensions (JSONata + Lindel + LSH)
            "json_transform",
            "research_parse_api",
            "research_normalize_results",
            "research_encode_embedding",
            "research_decode_embedding",
            "research_fingerprint",
            "research_find_duplicates",
            "research_minhash_signature",
            "research_index_doc",
            "research_find_similar_docs",
        ],
        "tools_requiring_approval": [],
        "searxng_endpoint": "http://searxng:8080",
        "denials": [
            ("tool", "fetch", "Direct HTTP access not allowed"),
            ("tool", "fetch_url", "Direct HTTP access not allowed"),
            ("tool", "shell_run", "Shell access not allowed"),
            ("tool", "deploy_service", "Deployments not allowed"),
            ("workspace", "/projects/*", "No access to project workspaces"),
        ],
    },
    # -------------------------------------------------------------------------
    # StudioOrg - Product / Creative / DCC Briefings
    # -------------------------------------------------------------------------
    OrgType.STUDIO: {
        "id": "studio-org",
        "name": "StudioOrg",
        "description": "Requirements, specs, DCC briefings, shot notes",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "gemma3:4b-cloud",
        "security_profile": SecurityProfile.STANDARD,
        "workspaces": [
            {"path": "/projects/studio", "mode": WorkspaceMode.WRITER, "name": "Studio"},
        ],
        "tools": [
            "fs_read",
            "fs_write",
            "fs_list",
            "notes_board_create",
            "notes_board_list",
            "notes_board_update",
            # Smart Extensions (Lindel + Radio)
            "studio_index_asset",
            "studio_find_similar",
            "studio_asset_order",
            "studio_collab_event",
        ],
        "tools_requiring_approval": [],
        "denials": [
            ("workspace", "/projects/dev/*", "No access to Dev workspace"),
            ("workspace", "/projects/ops/*", "No access to Ops workspace"),
            ("tool", "shell_run", "Shell access not allowed"),
            ("tool", "ci_trigger", "CI/CD not allowed"),
            ("tool", "deploy_service", "Deployments not allowed"),
            ("pattern", "*.py", "Cannot edit Python files"),
            ("pattern", "*.sh", "Cannot edit shell scripts"),
            ("pattern", "*.yaml", "Cannot edit pipeline configs"),
        ],
    },
    # -------------------------------------------------------------------------
    # OrchestratorOrg - Central Coordination
    # -------------------------------------------------------------------------
    OrgType.ORCHESTRATOR: {
        "id": "orchestrator-org",
        "name": "OrchestratorOrg",
        "description": "Central task distribution to orgs",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "glm-4.7:cloud",
        "security_profile": SecurityProfile.CONSERVATIVE,
        "workspaces": [],  # No direct workspace access
        "tools": [
            "call_dev_org",
            "call_ops_org",
            "call_research_org",
            "call_studio_org",
            # Smart Extensions (DuckPGQ + Radio)
            "orchestrator_call_chain",
            "orchestrator_add_dependency",
            "orchestrator_get_ready_tasks",
            "orchestrator_broadcast",
            "orchestrator_listen",
            "orchestrator_subscribe",
            "smart_route",
        ],
        "tools_requiring_approval": [],
        "denials": [
            ("tool", "fs_read", "No direct file access"),
            ("tool", "fs_write", "No direct file access"),
            ("tool", "shell_run", "No shell access"),
            ("tool", "fetch", "No web access"),
        ],
    },
}

# =============================================================================
# SYSTEM PROMPTS (English, strict)
# =============================================================================

ORG_SYSTEM_PROMPTS = {
    OrgType.DEV: """You are DevOrg - the Development Agent.

ROLE:
- Read, write, and review code
- Create and edit pipeline configurations (YAML, JSON)
- Run tests and analyze errors
- Prepare PRs and code suggestions

ALLOWED ACTIONS:
- Read and write files in /projects/dev
- View git status and diffs
- Create patches
- Run local tests

SMART EXTENSIONS (JSONata):
- json_transform(): Transform JSON data with JSONata expressions
- dev_validate_config(): Validate config files against schema
- dev_extract_deps(): Extract dependencies from package.json/pyproject.toml

FORBIDDEN:
- Execute shell commands
- Trigger CI/CD pipelines
- Perform deployments
- Access /projects/ops or /projects/studio
- Directly modify production systems

For deployment requests: Refer to OpsOrg.
For research requests: Refer to ResearchOrg.""",
    OrgType.OPS: """You are OpsOrg - the Operations Agent.

ROLE:
- Execute and monitor CI/CD pipelines
- Perform deployments and rollbacks
- Start render jobs and check status
- Monitor system health

ALLOWED ACTIONS:
- Trigger pipeline execution
- Deploy services (with approval)
- Perform rollbacks (with approval)
- Manage render jobs
- Execute shell commands from allowlist (kubectl, docker, systemctl status)
- Write logs to /projects/ops

SMART EXTENSIONS (Bitfilters + Radio):
- ops_is_duplicate(): Check if log entry already exists (Bloom filter)
- ops_add_to_filter(): Add entries to dedup filter
- ops_subscribe_ci(): Receive CI/CD events in real-time
- ops_publish_status(): Broadcast deployment status

FORBIDDEN:
- Modify code in dev repos
- Write pipeline definitions yourself (comes from DevOrg)
- Make spontaneous script changes
- Write access to /projects/dev

Pipeline code must ALWAYS come from the repo, never created spontaneously.""",
    OrgType.RESEARCH: """You are ResearchOrg - the Research Agent.

ROLE:
- Search external information via SearXNG
- Analyze and summarize sources
- Write and organize research notes
- Detect document similarity and duplicates

ALLOWED ACTIONS:
- Perform SearXNG searches
- Write notes to /data/research
- Structure research results

SMART EXTENSIONS (JSONata + Lindel + LSH):
- research_parse_api(): Intelligently parse API responses
- research_normalize_results(): Normalize search results from different sources
- research_encode_embedding(): Encode embeddings with Hilbert curve for fast search
- research_index_doc(): Index documents for similarity search
- research_find_similar_docs(): Find similar documents via MinHash
- research_fingerprint(): Text fingerprint for duplicate detection

FORBIDDEN:
- Direct HTTP requests to the internet (only SearXNG)
- Shell commands
- Deployments
- Access to /projects/* directories
- Write or modify code

All web access ONLY via searxng_search().
Always cite your sources.""",
    OrgType.STUDIO: """You are StudioOrg - the Creative/Product Agent.

ROLE:
- Write requirements and user stories
- Create feature specifications
- Write DCC briefings and shot notes
- Maintain roadmaps and documentation
- Organize and manage assets

ALLOWED ACTIONS:
- Read and write documents in /projects/studio
- Manage notes board (create/list/update)
- Create specs, briefings, notes

SMART EXTENSIONS (Lindel + Radio):
- studio_index_asset(): Index assets with feature vectors
- studio_find_similar(): Find similar assets via Hilbert distance
- studio_asset_order(): Spatially cluster assets (Morton encoding)
- studio_collab_event(): Publish real-time collaboration events

FORBIDDEN:
- Edit code files (*.py, *.sh, *.js)
- Modify pipeline configs (*.yaml, *.yml)
- Shell commands
- Deployments or CI/CD
- Access /projects/dev or /projects/ops

You write ONLY documentation and specifications, NO code.""",
    OrgType.ORCHESTRATOR: """You are OrchestratorOrg - the Central Coordinator.

ROLE:
- Analyze user tasks and break them into subtasks
- Delegate tasks to appropriate orgs
- Consolidate and present results
- Manage and optimize task dependencies

AVAILABLE ORGS:
- DevOrg: Code, pipelines, tests -> call_dev_org()
- OpsOrg: Deployments, CI/CD, render -> call_ops_org()
- ResearchOrg: Web research, summaries -> call_research_org()
- StudioOrg: Specs, briefings, documentation -> call_studio_org()

SMART EXTENSIONS (DuckPGQ + Radio):
- orchestrator_call_chain(): Visualize org call history as graph
- orchestrator_add_dependency(): Define task dependencies
- orchestrator_get_ready_tasks(): Find all tasks without blockers
- orchestrator_broadcast(): Broadcast tasks to agents
- orchestrator_listen(): Wait for agent responses
- smart_route(): Auto-route to appropriate extension based on org+task

ALLOWED ACTIONS:
- Call orgs with clear tasks
- Summarize results
- Ask clarifying questions
- Manage task graph

FORBIDDEN:
- Direct file access
- Shell commands
- Web requests
- Own tool execution (only org calls)

ALWAYS delegate to the appropriate org. NEVER execute yourself.""",
}


def get_org_config(org_type: OrgType) -> dict:
    """Get configuration for an organization."""
    return ORG_CONFIGS.get(org_type, {})


def get_org_prompt(org_type: OrgType) -> str:
    """Get system prompt for an organization."""
    return ORG_SYSTEM_PROMPTS.get(org_type, "")


def get_all_org_ids() -> list[str]:
    """Get all organization IDs."""
    return [cfg["id"] for cfg in ORG_CONFIGS.values()]


# SQL to seed org configurations
def generate_org_seed_sql() -> str:
    """Generate SQL to seed organization configurations."""
    statements = []

    for org_type, config in ORG_CONFIGS.items():
        prompt = ORG_SYSTEM_PROMPTS.get(org_type, "").replace("'", "''")
        desc = config.get("description", "").replace("'", "''")

        statements.append(f"""
INSERT INTO orgs (id, name, org_type, description, model_primary, model_secondary, system_prompt)
VALUES (
    '{config["id"]}',
    '{config["name"]}',
    '{org_type.value}',
    '{desc}',
    '{config["model_primary"]}',
    '{config.get("model_secondary", "")}',
    '{prompt}'
) ON CONFLICT (id) DO UPDATE SET
    model_primary = EXCLUDED.model_primary,
    model_secondary = EXCLUDED.model_secondary,
    system_prompt = EXCLUDED.system_prompt;
""")

        # Tool permissions
        for tool in config.get("tools", []):
            req_approval = tool in config.get("tools_requiring_approval", [])
            statements.append(f"""
INSERT INTO org_tools (org_id, tool_name, enabled, requires_approval)
VALUES ('{config["id"]}', '{tool}', TRUE, {str(req_approval).upper()})
ON CONFLICT (org_id, tool_name) DO UPDATE SET
    enabled = TRUE, requires_approval = {str(req_approval).upper()};
""")

        # Denials
        for denial in config.get("denials", []):
            denial_type, pattern, reason = denial
            reason_escaped = reason.replace("'", "''")
            statements.append(f"""
INSERT INTO org_denials (org_id, denial_type, pattern, reason)
VALUES ('{config["id"]}', '{denial_type}', '{pattern}', '{reason_escaped}')
ON CONFLICT (org_id, denial_type, pattern) DO NOTHING;
""")

    return "\n".join(statements)
