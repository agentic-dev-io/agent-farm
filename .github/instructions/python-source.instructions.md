---
applyTo: "src/**/*.py"
---

## Python Source Code Guidelines

When writing or modifying Python source code in the agent-farm repository, follow these standards for consistency, quality, and maintainability:

### Code Style & Formatting

1. **Ruff linter** - All code must pass Ruff linting with rules E, F, I, W
2. **Line length** - Maximum 100 characters per line (configured in pyproject.toml)
3. **Python version** - Target Python 3.11+ features and syntax
4. **Type hints** - Use type hints for all public APIs and function signatures
5. **Docstrings** - Include docstrings for all public functions, classes, and modules

### Import Organization

1. **Standard library first** - Group imports in order: standard library, third-party, local
2. **Alphabetical order** - Sort imports alphabetically within each group
3. **Explicit imports** - Prefer explicit imports over wildcard imports
4. **Ruff sorting** - Let Ruff handle import sorting automatically

Example import structure:
```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import duckdb

# Local imports
from agent_farm import utils
```

### Naming Conventions

1. **Functions/Variables** - Use `snake_case` (e.g., `load_extensions`, `connection_string`)
2. **Classes** - Use `PascalCase` (e.g., `DatabaseManager`, `MCPServer`)
3. **Constants** - Use `UPPER_SNAKE_CASE` (e.g., `DEFAULT_PORT`, `MAX_RETRIES`)
4. **Private members** - Prefix with single underscore (e.g., `_internal_method`)
5. **Module-level** - Avoid module-level code execution except in `main()` functions

### DuckDB Integration

1. **Connection management** - Create connections explicitly, don't rely on globals
2. **Resource cleanup** - Always close connections or use context managers
3. **SQL injection** - Use parameterized queries, avoid string formatting for SQL
4. **Extension loading** - Handle extension loading errors gracefully:
   ```python
   try:
       con.sql("INSTALL extension_name;")
   except Exception:
       print(f"Extension not available, trying community", file=sys.stderr)
       try:
           con.sql("INSTALL extension_name FROM community;")
       except Exception as e:
           print(f"Warning: Could not install extension: {e}", file=sys.stderr)
   
   try:
       con.sql("LOAD extension_name;")
   except Exception as e:
       print(f"Warning: Could not load extension: {e}", file=sys.stderr)
   ```
5. **SQL file loading** - Read SQL files and execute statements individually

### Error Handling

1. **Specific exceptions** - Catch specific exceptions rather than bare `except:`
2. **Error messages** - Provide descriptive error messages to stderr
3. **Graceful degradation** - Continue operation when non-critical features fail
4. **Logging** - Use print to stderr for errors and warnings
5. **Don't crash** - Server should not crash on individual operation failures

Example error handling:
```python
try:
    con.sql(statement)
except Exception as e:
    print(f"Error executing SQL: {e}", file=sys.stderr)
    # Continue execution, don't crash the server
```

### MCP Protocol Integration

1. **Transport** - Use stdio transport for MCP communication
2. **Port assignment** - Port 0 for stdio (auto-assign)
3. **Config discovery** - Check standard locations in order (project, user config, system)
4. **Table creation** - Use `CREATE OR REPLACE TABLE` for idempotency
5. **Schema validation** - Validate MCP configuration structure before use

### File Operations

1. **Path handling** - Use `pathlib.Path` for file path operations
2. **Relative paths** - Handle both absolute and relative paths correctly
3. **File existence** - Check file existence before operations
4. **Encoding** - Always specify encoding when reading text files (usually 'utf-8')
5. **Resource management** - Use context managers for file operations

### Configuration & Environment

1. **Environment variables** - Use `os.environ.get()` with sensible defaults
2. **Configuration files** - Support JSON configuration files for MCP servers
3. **Default values** - Always provide reasonable defaults
4. **Path resolution** - Resolve paths relative to appropriate base (home, cwd, etc.)

### Function Design

1. **Single responsibility** - Each function should have one clear purpose
2. **Parameter defaults** - Use default parameters for optional configuration
3. **Return values** - Be consistent with return types and values
4. **Side effects** - Minimize side effects, make them obvious when necessary
5. **Documentation** - Document parameters, return values, and exceptions

Example function signature:
```python
def load_sql_file(con: duckdb.DuckDBPyConnection, sql_file: Path) -> bool:
    """
    Load and execute SQL statements from a file.
    
    Args:
        con: DuckDB connection object
        sql_file: Path to SQL file to load
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        FileNotFoundError: If sql_file does not exist
    """
```

### Testing Considerations

1. **Testability** - Write code that can be easily tested
2. **Dependencies** - Make external dependencies injectable for testing
3. **Pure functions** - Prefer pure functions that are easier to test
4. **Mock-friendly** - Design code to work with mocked dependencies

### Performance

1. **Connection reuse** - Reuse DuckDB connections when possible
2. **Lazy loading** - Load extensions and resources only when needed
3. **Efficient queries** - Write efficient SQL queries
4. **Memory management** - Be mindful of memory usage with large result sets
5. **I/O operations** - Minimize file system and network I/O

### Main Entry Points

1. **main() function** - Define clear `main()` function for entry points
2. **if __name__ == "__main__"** - Use standard Python idiom for module execution
3. **Argument parsing** - Use argparse for command-line arguments if needed
4. **Exit codes** - Use appropriate exit codes (0 for success, non-zero for errors)

Example main function:
```python
def main():
    """Main entry point for agent-farm MCP server."""
    try:
        # Initialize and start server
        con = duckdb.connect(':memory:')
        load_extensions(con)
        load_macros(con)
        start_mcp_server(con)
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Security Considerations

1. **Input validation** - Validate and sanitize all external inputs
2. **SQL injection** - Use parameterized queries, never string formatting
3. **Path traversal** - Validate file paths to prevent directory traversal attacks
4. **Secrets** - Never hardcode secrets, use environment variables or config files
5. **Least privilege** - Run with minimal required permissions

### Documentation

1. **Module docstrings** - Include module-level docstring describing purpose
2. **Function docstrings** - Document all public functions with parameters and return values
3. **Inline comments** - Use comments to explain "why", not "what"
4. **Type hints** - Use type hints to document expected types
5. **README updates** - Update README.md when adding user-facing features

### Dependencies

1. **Minimal dependencies** - Add new dependencies only when necessary
2. **Version constraints** - Specify appropriate version constraints in pyproject.toml
3. **Standard library** - Prefer standard library when possible
4. **Security** - Keep dependencies updated for security patches

### Continuous Integration

Before committing code:
```bash
# Format and lint code
uv run ruff check --fix src/
uv run ruff format src/

# Run tests
uv run pytest tests/ -v

# Verify package builds
uv build
```
