"""
Agent Farm MCP Server - DuckDB-powered Spec Engine

The Agent Farm uses a DuckDB-based Spec Engine as the central "Spec-OS" for all agents.
The Spec Engine manages specifications for:
- Agents, skills, workflows
- APIs/protocols (HTTP/MCP/OpenAPI/GraphQL)
- JSON Schemas for validation
- Prompt/plan templates (MiniJinja)
- Task templates, UIs, Open-Responses

Entry point for the MCP server.
"""

import json
import os
import sys
from pathlib import Path

import duckdb


def _has_non_comment_content(stmt: str) -> bool:
    """Check if a SQL statement has any non-comment content."""
    for ln in stmt.split("\n"):
        ln = ln.strip()
        if ln and not ln.startswith("--"):
            return True
    return False


def split_sql_statements(sql_content: str) -> list[str]:
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
            if stmt and _has_non_comment_content(stmt):
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    if current:
        stmt = "".join(current).strip()
        if stmt and _has_non_comment_content(stmt):
            statements.append(stmt)

    return statements


def find_mcp_config() -> list[tuple[str, dict]]:
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


def extract_mcp_servers(configs: list[tuple[str, dict]]) -> dict:
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


def setup_mcp_tables(con: duckdb.DuckDBPyConnection, servers: dict) -> None:
    """
    Create tables with discovered MCP server info for SQL access.
    """
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
            "INSERT INTO mcp_servers VALUES (?, ?, ?, ?, ?)",
            [name, command, args, env, source],
        )

    print(f"Registered {len(servers)} MCP servers in mcp_servers table", file=sys.stderr)


def load_core_extensions(con: duckdb.DuckDBPyConnection) -> list[str]:
    """
    Load core DuckDB extensions required for the Agent Farm.
    Returns list of successfully loaded extensions.
    """
    # Extensions in priority order
    # Required extensions are loaded first, optional ones after
    extensions = [
        # Spec Engine core (required)
        ("json", True),
        ("minijinja", True),  # Template rendering
        ("json_schema", True),  # JSON Schema validation
        ("duckdb_mcp", True),  # MCP integration
        # HTTP & Data (required)
        ("httpfs", True),
        ("http_client", True),
        ("icu", True),
        # HTTP Server (optional but recommended)
        ("httpserver", False),
        # === INTELLIGENCE LAYER ===
        # DuckLake - Persistent Lakehouse for agent memory
        ("ducklake", False),  # Time travel, snapshots, schema evolution
        # Vector Similarity Search - RAG/Embeddings
        ("vss", False),  # Vector similarity search for semantic retrieval
        # Full-text search for hybrid retrieval
        ("fts", False),  # Full-text search
        # === ADVANCED DATA STRUCTURES ===
        ("jsonata", False),  # JSONata query/transform
        ("duckpgq", False),  # Property graphs for spec relationships
        ("bitfilters", False),  # Bloom/MinHash for similarity/dedup
        ("lindel", False),  # Space-filling curves for geo/spatial
        # === TEXT PROCESSING ===
        ("htmlstringify", False),  # HTML to text for web scraping
        ("lsh", False),  # Locality Sensitive Hashing for near-dedup
        # === EXTENDED DATA SOURCES ===
        ("shellfs", False),  # Shell commands as tables
        ("zipfs", False),  # ZIP archive access for artifacts
        # === REAL-TIME ===
        ("radio", False),  # WebSocket & Redis PubSub for sync
    ]

    loaded = []
    for ext, required in extensions:
        try:
            con.sql(f"INSTALL {ext};")
            con.sql(f"LOAD {ext};")
            loaded.append(ext)
            print(f"Loaded extension: {ext}", file=sys.stderr)
        except Exception:
            try:
                con.sql(f"INSTALL {ext} FROM community;")
                con.sql(f"LOAD {ext};")
                loaded.append(ext)
                print(f"Loaded extension {ext} from community", file=sys.stderr)
            except Exception as e:
                if required:
                    print(f"REQUIRED extension {ext} failed: {e}", file=sys.stderr)
                else:
                    print(f"Skipping optional extension {ext}: {e}", file=sys.stderr)

    return loaded


def create_runtime_tables(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create runtime tables for session management, auditing, and approvals.
    These are operational tables, not specifications (specs live in spec_objects).
    """
    con.sql("""
        -- Audit log for all agent actions
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            timestamp TIMESTAMP DEFAULT now(),
            entry_type VARCHAR NOT NULL,  -- 'tool_call', 'spec_access', 'feedback', 'learning'
            spec_id INTEGER,              -- Reference to spec_objects if relevant
            tool_name VARCHAR,
            parameters JSON,
            result JSON,
            decision VARCHAR,             -- 'allowed', 'denied', 'approved', 'rejected'
            violations VARCHAR[]
        );

        -- Session state for active agent sessions
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id VARCHAR PRIMARY KEY,
            agent_spec_id INTEGER,        -- Reference to spec_objects (kind='agent')
            started_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'active',
            context JSON DEFAULT '{}',    -- Session context/state
            messages JSON DEFAULT '[]'
        );

        -- Pending approvals for sensitive operations
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            spec_id INTEGER,              -- Reference to spec_objects
            tool_name VARCHAR NOT NULL,
            tool_params JSON,
            reason VARCHAR,
            created_at TIMESTAMP DEFAULT now(),
            status VARCHAR DEFAULT 'pending',
            resolved_at TIMESTAMP,
            resolved_by VARCHAR
        );

        -- Inter-organization calls (for swarm coordination)
        CREATE TABLE IF NOT EXISTS org_calls (
            id INTEGER PRIMARY KEY,
            session_id VARCHAR NOT NULL,
            caller_spec_id INTEGER NOT NULL,  -- Reference to spec_objects (kind='org')
            target_spec_id INTEGER NOT NULL,  -- Reference to spec_objects (kind='org')
            task VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'pending',
            result JSON,
            created_at TIMESTAMP DEFAULT now(),
            completed_at TIMESTAMP
        );

        -- Notes board for collaboration
        CREATE TABLE IF NOT EXISTS notes_board (
            id VARCHAR PRIMARY KEY,
            project VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content VARCHAR,
            note_type VARCHAR DEFAULT 'general',
            status VARCHAR DEFAULT 'open',
            created_by VARCHAR DEFAULT 'system',
            spec_refs JSON DEFAULT '[]',  -- References to related specs
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );

        -- Sequences
        CREATE SEQUENCE IF NOT EXISTS audit_seq START 1;
        CREATE SEQUENCE IF NOT EXISTS approval_seq START 1;
        CREATE SEQUENCE IF NOT EXISTS org_call_seq START 1;
    """)
    print("Runtime tables created.", file=sys.stderr)


def load_sql_macros(con: duckdb.DuckDBPyConnection) -> int:
    """
    Load SQL macros from the sql/ directory.
    Returns total number of macros loaded.
    """
    sql_dir = os.path.join(os.path.dirname(__file__), "sql")
    total_loaded = 0

    if os.path.isdir(sql_dir):
        sql_files = sorted(f for f in os.listdir(sql_dir) if f.endswith(".sql"))
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
    else:
        print("Warning: sql/ directory not found, no macros loaded", file=sys.stderr)

    return total_loaded


def create_agent_tables(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create agent infrastructure tables (workspaces, security_policy, etc.).
    These must exist before SQL macros are loaded, as macros reference them.
    """
    from .schemas import AGENT_TABLES_SQL

    for stmt in AGENT_TABLES_SQL.split(";"):
        stmt = stmt.strip()
        if stmt and _has_non_comment_content(stmt):
            try:
                con.sql(stmt)
            except Exception as e:
                print(f"Error creating agent table: {e}", file=sys.stderr)
    print("Agent infrastructure tables created.", file=sys.stderr)


def main():
    """
    Main entry point for the Agent Farm MCP Server.

    Initialization order:
    1. Create DuckDB connection
    2. Load core extensions
    3. Initialize Spec Engine (schema, macros, seed data)
    4. Discover MCP configurations
    5. Register Python UDFs (before SQL macros, as macros may reference them)
    6. Create agent infrastructure tables (before SQL macros reference them)
    7. Create runtime tables (sessions, audit, approvals)
    8. Load SQL macros
    9. Seed organization configs
    10. Start MCP Server
    """
    # Get database path from environment or use in-memory
    db_path = os.environ.get("DUCKDB_DATABASE", ":memory:")

    # Initialize DuckDB connection
    con = duckdb.connect(database=db_path)
    print(f"Initializing Agent Farm (db: {db_path})...", file=sys.stderr)

    # 1. Load Core Extensions
    print("Loading extensions...", file=sys.stderr)
    loaded_extensions = load_core_extensions(con)

    # 2. Initialize Spec Engine (the heart of the system)
    print("Initializing Spec Engine...", file=sys.stderr)
    try:
        from .spec_engine import get_spec_engine, register_spec_engine_tools

        spec_engine = get_spec_engine(con)
        spec_tools = register_spec_engine_tools(con)
        print(f"Spec Engine: Registered {len(spec_tools)} UDFs", file=sys.stderr)
    except ImportError as e:
        print(f"Spec Engine module not available: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error initializing Spec Engine: {e}", file=sys.stderr)

    # 3. MCP Config Discovery
    print("Discovering MCP configurations...", file=sys.stderr)
    mcp_configs = find_mcp_config()
    mcp_servers = extract_mcp_servers(mcp_configs)

    if mcp_servers:
        setup_mcp_tables(con, mcp_servers)
    else:
        print("No MCP configurations found", file=sys.stderr)
        con.sql("""
            CREATE OR REPLACE TABLE mcp_servers (
                name VARCHAR,
                command VARCHAR,
                args VARCHAR[],
                env JSON,
                source_config VARCHAR
            )
        """)

    # 4. Register Python UDFs BEFORE SQL macros (macros reference getenv etc.)
    try:
        from .udfs import register_udfs

        registered = register_udfs(con)
        print(f"Registered {len(registered)} UDFs: {', '.join(registered)}", file=sys.stderr)
    except ImportError:
        print("UDFs module not available, skipping", file=sys.stderr)
    except Exception as e:
        print(f"Error registering UDFs: {e}", file=sys.stderr)

    # 5. Create Agent Infrastructure Tables (workspaces, security_policy, etc.)
    #    Must exist before SQL macros are loaded, as macros reference these tables.
    print("Creating agent infrastructure tables...", file=sys.stderr)
    create_agent_tables(con)

    # 6. Create Runtime Tables (sessions, audit, approvals)
    print("Creating runtime tables...", file=sys.stderr)
    create_runtime_tables(con)

    # 7. Load SQL Macros
    print("Loading SQL macros...", file=sys.stderr)
    total_macros = load_sql_macros(con)
    print(f"Total: {total_macros} macros loaded.", file=sys.stderr)

    # 8. Seed Organization Configurations
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

    # 9. Create extension info table
    con.sql(f"""
        CREATE OR REPLACE TABLE loaded_extensions AS
        SELECT unnest({loaded_extensions!r}::VARCHAR[]) as extension_name
    """)

    # 9. Optionally start HTTP server for Spec Engine
    http_port = os.environ.get("SPEC_ENGINE_HTTP_PORT")
    http_api_key = os.environ.get("SPEC_ENGINE_API_KEY")
    if http_port:
        try:
            port = int(http_port)
            if http_api_key:
                con.sql(f"SELECT httpserve_start('0.0.0.0', {port}, 'X-API-Key {http_api_key}')")
            else:
                con.sql(f"SELECT httpserve_start('0.0.0.0', {port})")
            print(f"Spec Engine HTTP server started on port {port}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to start HTTP server: {e}", file=sys.stderr)

    # 10. Start MCP Server
    print("Starting MCP Server...", file=sys.stderr)
    try:
        con.sql("SELECT mcp_server_start('stdio', 'localhost', 0, '{}')")
    except Exception as e:
        print(f"Error starting MCP Server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
