import json
import os
import sys
from pathlib import Path

import duckdb


def split_sql_statements(sql_content):
    """Split SQL content into statements, respecting string literals."""
    statements = []
    current = []
    in_string = False
    string_char = None

    i = 0
    while i < len(sql_content):
        char = sql_content[i]

        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            current.append(char)
        elif char == string_char and in_string:
            if i + 1 < len(sql_content) and sql_content[i + 1] == string_char:
                current.append(char)
                current.append(char)
                i += 1
            else:
                in_string = False
                string_char = None
                current.append(char)
        elif char == ";" and not in_string:
            stmt = "".join(current).strip()
            if stmt and not stmt.startswith("--"):
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    if current:
        stmt = "".join(current).strip()
        if stmt and not stmt.startswith("--"):
            statements.append(stmt)

    return statements


def find_mcp_config():
    """
    Discover MCP configuration files in standard locations.
    Returns list of (config_path, config_data) tuples.
    """
    config_locations = [
        # Project-local
        Path.cwd() / "mcp.json",
        Path.cwd() / ".mcp.json",
        Path.cwd() / "mcp_config.json",
        # Claude Desktop standard locations
        Path.home() / ".config" / "claude" / "claude_desktop_config.json",
        # Windows
        Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        # macOS
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        # Generic MCP config
        Path.home() / ".mcp" / "config.json",
    ]

    found_configs = []
    for config_path in config_locations:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                found_configs.append((str(config_path), config_data))
                print(f"Found MCP config: {config_path}", file=sys.stderr)
            except Exception as e:
                print(f"Error reading {config_path}: {e}", file=sys.stderr)

    return found_configs


def extract_mcp_servers(configs):
    """
    Extract MCP server definitions from config files.
    Returns dict of server_name -> server_config
    """
    servers = {}
    for config_path, config_data in configs:
        # Handle claude_desktop_config.json format
        if "mcpServers" in config_data:
            for name, server_config in config_data["mcpServers"].items():
                servers[name] = {"source": config_path, **server_config}
        # Handle simple mcp.json format
        elif "servers" in config_data:
            for name, server_config in config_data["servers"].items():
                servers[name] = {"source": config_path, **server_config}
    return servers


def setup_mcp_tables(con, servers):
    """
    Create tables with discovered MCP server info for SQL access.
    """
    # Create table for MCP servers
    con.sql("""
        CREATE OR REPLACE TABLE mcp_servers (
            name VARCHAR,
            command VARCHAR,
            args VARCHAR[],
            env JSON,
            source_config VARCHAR
        )
    """)

    for name, config in servers.items():
        command = config.get("command", "")
        args = config.get("args", [])
        env = json.dumps(config.get("env", {}))
        source = config.get("source", "")

        con.execute(
            """
            INSERT INTO mcp_servers VALUES (?, ?, ?, ?, ?)
        """,
            [name, command, args, env, source],
        )

    print(f"Registered {len(servers)} MCP servers in mcp_servers table", file=sys.stderr)


def main():
    # Initialize DuckDB connection
    con = duckdb.connect(database=":memory:")

    print("Initializing queries...", file=sys.stderr)

    # 1. Install & Load Extensions
    extensions = [
        # Core: HTTP & Data Formats
        "httpfs",
        "http_client",
        "json",
        "icu",
        "duckdb_mcp",
        # Advanced Data Structs & Logic
        "jsonata",
        "duckpgq",
        "bitfilters",
        "lindel",
        # AI/LLM Stack
        "vss",  # Vector Similarity Search (native)
        # Text Processing
        "htmlstringify",  # HTML to plain text
        "lsh",  # Locality Sensitive Hashing
        # Extended Data Sources
        "shellfs",  # Shell commands as tables
        "zipfs",  # Read ZIP archives
        # Real-time (optional, may fail on some platforms)
        "radio",  # WebSocket & Redis PubSub
    ]

    loaded_extensions = []
    for ext in extensions:
        try:
            con.sql(f"INSTALL {ext};")
            con.sql(f"LOAD {ext};")
            loaded_extensions.append(ext)
            print(f"Loaded extension: {ext}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to load {ext}: {e}", file=sys.stderr)
            try:
                con.sql(f"INSTALL {ext} FROM community;")
                con.sql(f"LOAD {ext};")
                loaded_extensions.append(ext)
                print(f"Loaded extension {ext} from community", file=sys.stderr)
            except Exception as e2:
                print(f"Skipping {ext}: {e2}", file=sys.stderr)

    # 2. MCP Config Discovery
    print("Discovering MCP configurations...", file=sys.stderr)
    mcp_configs = find_mcp_config()
    mcp_servers = extract_mcp_servers(mcp_configs)

    if mcp_servers:
        setup_mcp_tables(con, mcp_servers)
    else:
        print("No MCP configurations found", file=sys.stderr)
        # Create empty table for consistency
        con.sql("""
            CREATE OR REPLACE TABLE mcp_servers (
                name VARCHAR,
                command VARCHAR,
                args VARCHAR[],
                env JSON,
                source_config VARCHAR
            )
        """)

    # 3. Create Agent Config Tables
    print("Creating agent config tables...", file=sys.stderr)
    con.sql("""
        -- Agent configuration
        CREATE TABLE IF NOT EXISTS agent_config (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL DEFAULT 'Desktop Agent',
            role VARCHAR NOT NULL DEFAULT 'assistant',
            security_profile VARCHAR NOT NULL DEFAULT 'standard',
            model_backend VARCHAR NOT NULL DEFAULT 'ollama_local',
            model_name VARCHAR DEFAULT 'llama3.2',
            consent_given BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );

        -- Workspace definitions
        CREATE TABLE IF NOT EXISTS workspaces (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,
            path VARCHAR NOT NULL,
            name VARCHAR,
            mode VARCHAR NOT NULL DEFAULT 'readOnly',
            allowed_patterns VARCHAR[],
            denied_patterns VARCHAR[]
        );

        -- MCP server configs for agent (separate from discovered mcp_servers)
        CREATE TABLE IF NOT EXISTS agent_mcp_servers (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,
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
            agent_id VARCHAR PRIMARY KEY,
            shell_enabled BOOLEAN DEFAULT FALSE,
            shell_allowlist VARCHAR[],
            shell_blocklist VARCHAR[] DEFAULT [
                'rm -rf', 'rm -r /', 'mkfs', 'dd if=', ':(){:|:&};:',
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

        -- Audit log
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP DEFAULT now(),
            entry_type VARCHAR NOT NULL,
            tool_name VARCHAR,
            parameters JSON,
            result JSON,
            decision VARCHAR,
            violations VARCHAR[]
        );

        -- Session state
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR,
            started_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'active',
            messages JSON DEFAULT '[]'
        );

        -- Pending approvals (SR-6.5)
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            agent_id VARCHAR,
            tool_name VARCHAR NOT NULL,
            tool_params JSON,
            reason VARCHAR,
            created_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'pending',
            resolved_at TIMESTAMP,
            resolved_by VARCHAR
        );

        -- Create sequence for audit log if not exists
        CREATE SEQUENCE IF NOT EXISTS audit_seq START 1;

        -- Organization tables
        CREATE TABLE IF NOT EXISTS orgs (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            org_type VARCHAR NOT NULL,
            description VARCHAR,
            model_primary VARCHAR NOT NULL,
            model_secondary VARCHAR,
            system_prompt TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS org_tools (
            org_id VARCHAR NOT NULL,
            tool_name VARCHAR NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            requires_approval BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (org_id, tool_name)
        );

        CREATE TABLE IF NOT EXISTS org_denials (
            org_id VARCHAR NOT NULL,
            denial_type VARCHAR NOT NULL,
            pattern VARCHAR NOT NULL,
            reason VARCHAR,
            PRIMARY KEY (org_id, denial_type, pattern)
        );

        CREATE TABLE IF NOT EXISTS org_calls (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            caller_org VARCHAR NOT NULL,
            target_org VARCHAR NOT NULL,
            task VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'pending',
            result JSON,
            created_at TIMESTAMP DEFAULT now(),
            completed_at TIMESTAMP
        );

        -- Notes board for StudioOrg
        CREATE TABLE IF NOT EXISTS notes_board (
            id VARCHAR PRIMARY KEY,
            project VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content TEXT,
            note_type VARCHAR DEFAULT 'general',
            status VARCHAR DEFAULT 'open',
            created_by VARCHAR DEFAULT 'studio-org',
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)
    print("Agent config tables created.", file=sys.stderr)

    # 3b. Seed organization configurations
    try:
        from .orgs import generate_org_seed_sql

        org_seed_sql = generate_org_seed_sql()
        for stmt in org_seed_sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    con.sql(stmt)
                except Exception as e:
                    print(f"Error seeding org: {e}", file=sys.stderr)
        print("Organization configs seeded.", file=sys.stderr)
    except ImportError:
        print("Orgs module not available, skipping seed", file=sys.stderr)
    except Exception as e:
        print(f"Error seeding orgs: {e}", file=sys.stderr)

    # 4. Load SQL Macros from sql/ directory
    sql_dir = os.path.join(os.path.dirname(__file__), "sql")
    if os.path.isdir(sql_dir):
        sql_files = sorted(f for f in os.listdir(sql_dir) if f.endswith(".sql"))
        total_loaded = 0
        for sql_file in sql_files:
            sql_path = os.path.join(sql_dir, sql_file)
            with open(sql_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
            statements = split_sql_statements(sql_script)
            loaded = 0
            for statement in statements:
                lines = [
                    ln
                    for ln in statement.split("\n")
                    if ln.strip() and not ln.strip().startswith("--")
                ]
                if not lines:
                    continue
                try:
                    con.sql(statement)
                    loaded += 1
                except Exception as e:
                    print(f"Error in {sql_file}: {e}", file=sys.stderr)
            total_loaded += loaded
            print(f"Loaded {loaded} macros from {sql_file}", file=sys.stderr)
        print(f"Total: {total_loaded} macros loaded.", file=sys.stderr)
    else:
        # Fallback to legacy macros.sql
        macros_path = os.path.join(os.path.dirname(__file__), "macros.sql")
        if os.path.exists(macros_path):
            with open(macros_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
            statements = split_sql_statements(sql_script)
            loaded = 0
            for statement in statements:
                lines = [
                    ln
                    for ln in statement.split("\n")
                    if ln.strip() and not ln.strip().startswith("--")
                ]
                if not lines:
                    continue
                try:
                    con.sql(statement)
                    loaded += 1
                except Exception as e:
                    print(f"Error executing macro: {e}", file=sys.stderr)
            print(f"Loaded {loaded} macros from macros.sql", file=sys.stderr)

    # 5. Register Python UDFs
    try:
        from .udfs import register_udfs

        registered = register_udfs(con)
        print(f"Registered {len(registered)} UDFs: {', '.join(registered)}", file=sys.stderr)
    except ImportError:
        print("UDFs module not available, skipping", file=sys.stderr)
    except Exception as e:
        print(f"Error registering UDFs: {e}", file=sys.stderr)

    # 6. Create extension info table
    con.sql(f"""
        CREATE OR REPLACE TABLE loaded_extensions AS
        SELECT unnest({loaded_extensions!r}::VARCHAR[]) as extension_name
    """)

    # 7. Start MCP Server
    print("Starting MCP Server...", file=sys.stderr)
    try:
        con.sql("SELECT mcp_server_start('stdio', 'localhost', 0, '{}')")
    except Exception as e:
        print(f"Error starting MCP Server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
