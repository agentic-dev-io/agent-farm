import json
import os
import sys
from pathlib import Path

import duckdb


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

    # 3. Load Macros
    macros_path = os.path.join(os.path.dirname(__file__), "macros.sql")
    if os.path.exists(macros_path):
        with open(macros_path, "r") as f:
            sql_script = f.read()
            for statement in sql_script.split(";"):
                if statement.strip():
                    try:
                        con.sql(statement)
                    except Exception as e:
                        print(f"Error executing macro SQL: {e}", file=sys.stderr)
        print("Loaded macros.", file=sys.stderr)

    # 4. Create extension info table
    con.sql(f"""
        CREATE OR REPLACE TABLE loaded_extensions AS
        SELECT unnest({loaded_extensions!r}::VARCHAR[]) as extension_name
    """)

    # 5. Start MCP Server
    print("Starting MCP Server...", file=sys.stderr)
    try:
        con.sql("SELECT mcp_server_start('stdio', 'localhost', 0, '{}')")
    except Exception as e:
        print(f"Error starting MCP Server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
