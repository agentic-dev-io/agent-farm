"""
Minimal schema definitions for Secure Desktop Agent.

These are simple data structures for config - the actual logic
lives in SQL macros and DuckDB tables.
"""

from enum import Enum


class AgentRole(str, Enum):
    CODE = "code"
    RESEARCH = "research"
    ORGANIZER = "organizer"
    ASSISTANT = "assistant"
    # Org-specific roles
    DEVELOPER = "developer"
    OPERATOR = "operator"
    RESEARCHER = "researcher"
    CREATIVE = "creative"
    ORCHESTRATOR = "orchestrator"


class OrgType(str, Enum):
    """Organization types for multi-agent system."""

    DEV = "dev"  # Development / Pipelines-as-Code
    OPS = "ops"  # Operations / CI/CD & Render
    RESEARCH = "research"  # Research via SearXNG
    STUDIO = "studio"  # Product / Creative / DCC briefings
    ORCHESTRATOR = "orchestrator"  # Central coordination


class WorkspaceMode(str, Enum):
    READ_ONLY = "readOnly"
    WRITER = "writer"
    OPERATOR = "operator"


class SecurityProfile(str, Enum):
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    POWER = "power"


class ModelBackend(str, Enum):
    CLAUDE_CLOUD = "claude_cloud"
    OLLAMA_LOCAL = "ollama_local"


# SQL for creating agent config tables
AGENT_TABLES_SQL = """
-- Agent configuration
CREATE TABLE IF NOT EXISTS agent_config (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL DEFAULT 'Desktop Agent',
    role VARCHAR NOT NULL DEFAULT 'assistant',
    security_profile VARCHAR NOT NULL DEFAULT 'standard',
    model_backend VARCHAR NOT NULL DEFAULT 'ollama_local',
    model_name VARCHAR DEFAULT 'kimi-k2.5:cloud',
    consent_given BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Workspace definitions
CREATE TABLE IF NOT EXISTS workspaces (
    id VARCHAR PRIMARY KEY,
    agent_id VARCHAR REFERENCES agent_config(id),
    path VARCHAR NOT NULL,
    name VARCHAR,
    mode VARCHAR NOT NULL DEFAULT 'readOnly',
    allowed_patterns VARCHAR[],
    denied_patterns VARCHAR[]
);

-- MCP server configs for agent (separate from discovered mcp_servers)
CREATE TABLE IF NOT EXISTS agent_mcp_servers (
    id VARCHAR PRIMARY KEY,
    agent_id VARCHAR REFERENCES agent_config(id),
    transport VARCHAR DEFAULT 'stdio',
    endpoint VARCHAR,
    command VARCHAR,
    args VARCHAR[],
    enabled BOOLEAN DEFAULT TRUE,
    allowed_tools VARCHAR[],
    disallowed_tools VARCHAR[]
);

-- Security policy
CREATE TABLE IF NOT EXISTS security_policy (
    agent_id VARCHAR PRIMARY KEY REFERENCES agent_config(id),
    shell_enabled BOOLEAN DEFAULT FALSE,
    shell_allowlist VARCHAR[],
    shell_blocklist VARCHAR[] DEFAULT [
        'rm -rf', 'rm -r /', 'mkfs', 'dd if=',
        'chmod -R 777', 'curl | sh', 'wget | sh', '> /dev/sd'
    ],
    web_enabled BOOLEAN DEFAULT TRUE,
    allowed_domains VARCHAR[],
    blocked_domains VARCHAR[],
    sensitive_patterns VARCHAR[] DEFAULT [
        '*.env', '.env*', '*credentials*', '*secret*',
        '*.pem', '*.key', '*password*'
    ]
);
"""

# Role-specific system prompts
ROLE_PROMPTS = {
    AgentRole.CODE: """You are a code-focused assistant. Read, analyze, write and debug code.
Security: Only access files in configured workspaces. Never execute without approval.""",
    AgentRole.RESEARCH: """You are a research assistant. Search, analyze and summarize information.
Security: Only access approved domains. Cite sources.""",
    AgentRole.ORGANIZER: """You are an organizational assistant. Manage files and tasks.
Security: Only organize within workspaces. Never delete without approval.""",
    AgentRole.ASSISTANT: """You are a general assistant. Help with various tasks.
Security: Follow least privilege. Request approval for sensitive operations.""",
}

# Security profile defaults
SECURITY_DEFAULTS = {
    SecurityProfile.CONSERVATIVE: {
        "shell_enabled": False,
        "default_workspace_mode": WorkspaceMode.READ_ONLY,
    },
    SecurityProfile.STANDARD: {
        "shell_enabled": False,
        "default_workspace_mode": WorkspaceMode.WRITER,
    },
    SecurityProfile.POWER: {
        "shell_enabled": True,
        "default_workspace_mode": WorkspaceMode.OPERATOR,
    },
}
