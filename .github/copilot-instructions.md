# GitHub Copilot Instructions for agent-farm

## Project Overview
**agent-farm** is a DuckDB-powered MCP (Model Context Protocol) Server that provides SQL macros for LLM agents, enabling web search, Python execution, RAG capabilities, and more through a unified SQL interface.

## Core Architecture

### Technology Stack
- **Language**: Python 3.11+
- **Package Manager**: uv (modern, fast Python package manager)
- **Database**: DuckDB 1.1.0+ with extensions
- **Protocol**: MCP (Model Context Protocol)
- **Container**: Docker
- **Linter**: Ruff
- **Testing**: pytest

### Key Components
1. **MCP Server** (`src/agent_farm/main.py`): Entry point that initializes DuckDB, loads extensions, and starts MCP server
2. **SQL Macros** (`src/agent_farm/macros.sql`): DuckDB macros for LLM integration, web search, shell execution, etc.
3. **Extensions**: DuckDB extensions for HTTP, JSON, VSS, MCP protocol, and more

## Coding Standards

### Python Style
- **Line Length**: 100 characters (configured in pyproject.toml)
- **Target Version**: Python 3.11
- **Linter**: Ruff with rules E, F, I, W
- **Type Hints**: Use typing for public APIs
- **Imports**: Keep organized with Ruff's import sorting

### Code Organization
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
- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **SQL Macros**: `snake_case` (e.g., `ollama_chat`, `ddg_search`)

## SQL Macro Development

### Macro Structure
```sql
-- Clear documentation comment
CREATE OR REPLACE MACRO macro_name(param1, param2) AS (
    SELECT ...
);
```

### Best Practices
1. **Always use `CREATE OR REPLACE`**: Allows reloading macros without errors
2. **Document parameters**: Add comments explaining each parameter
3. **Error handling**: Use try-catch where applicable
4. **Null safety**: Handle NULL inputs gracefully
5. **Performance**: Minimize nested queries, use CTEs for readability

### Common Patterns

#### HTTP Requests
```sql
CREATE OR REPLACE MACRO fetch_api(url) AS (
    SELECT http_get(url).body
);
```

#### LLM Integration
```sql
CREATE OR REPLACE MACRO llm_call(model, prompt) AS (
    SELECT json_extract_string(
        http_post(
            'http://localhost:11434/api/generate',
            headers := MAP {'Content-Type': 'application/json'},
            body := json_object('model', model, 'prompt', prompt, 'stream', false)
        ).body,
        '$.response'
    )
);
```

## MCP Protocol Integration

### Server Configuration
- **Transport**: stdio (standard input/output)
- **Port**: 0 (auto-assign for stdio)
- **Host**: localhost

### Discovery Mechanism
The server auto-discovers MCP configurations from:
1. Project-local: `./mcp.json`, `./.mcp.json`, `./mcp_config.json`
2. Claude Desktop: `~/.config/claude/claude_desktop_config.json`
3. Generic: `~/.mcp/config.json`

### Adding MCP Tables
When adding new MCP-related functionality:
```python
con.sql("""
    CREATE OR REPLACE TABLE table_name (
        column1 TYPE,
        column2 TYPE
    )
""")
```

## Extension Management

### Loading Extensions
```python
extensions = ['httpfs', 'json', 'http_client']
for ext in extensions:
    try:
        con.sql(f"INSTALL {ext};")
        con.sql(f"LOAD {ext};")
    except Exception:
        # Try community extensions
        con.sql(f"INSTALL {ext} FROM community;")
        con.sql(f"LOAD {ext};")
```

### Available Extensions
- **Core**: httpfs, json, icu, vss, lindel
- **Community**: http_client, duckdb_mcp, jsonata, shellfs, zipfs, htmlstringify

## Testing Guidelines

### Running Tests
```bash
# Install dev dependencies
uv sync --dev

# Run all tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_macros.py

# Run with coverage
uv run pytest --cov=agent_farm tests/
```

### Test Structure
```python
def test_feature():
    """Test description"""
    con = duckdb.connect(':memory:')
    # Setup
    con.sql("LOAD extension;")
    # Execute
    result = con.sql("SELECT macro()").fetchone()
    # Assert
    assert result is not None
```

### Mock External Dependencies
- Mock HTTP calls for deterministic tests
- Use in-memory DuckDB for speed
- Avoid actual Ollama/LLM calls in tests

## Build & Release Process

### Local Development
```bash
# Clone and setup
git clone https://github.com/bjoernbethge/agent-farm.git
cd agent-farm
uv sync --dev

# Run locally
uv run agent-farm
# or
uv run python -m agent_farm
```

### Linting
```bash
# Check code
uv run ruff check src/ tests/

# Auto-fix
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/
```

### Building Package
```bash
# Build distribution
uv build

# Install locally
uv pip install -e .
```

### Docker
```bash
# Build image
docker build -t agent-farm .

# Run container
docker run -v /data:/data -p 8080:8080 agent-farm
```

## Common Development Tasks

### Adding a New SQL Macro
1. Open `src/agent_farm/macros.sql`
2. Add macro with documentation:
   ```sql
   -- Description of what the macro does
   -- param1: Description of parameter
   CREATE OR REPLACE MACRO new_macro(param1) AS (
       SELECT ...
   );
   ```
3. Test in DuckDB CLI or add test
4. Update README.md if user-facing

### Adding a New Extension
1. Add to extensions list in `main.py`
2. Handle installation errors gracefully
3. Test with and without extension
4. Document in README.md

### Adding MCP Server Configuration
1. Update `find_mcp_config()` if new location needed
2. Modify `extract_mcp_servers()` for new format
3. Update `setup_mcp_tables()` for schema changes

## Error Handling

### Python Errors
```python
try:
    con.sql(statement)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    # Don't crash the server, continue
```

### SQL Errors
- Use `TRY()` function for error-prone operations
- Validate inputs before passing to macros
- Return NULL or empty result instead of failing

## Documentation Standards

### Code Comments
- Explain **why**, not **what**
- Document complex algorithms
- Reference external resources/specs
- Keep comments up-to-date

### README Updates
When adding user-facing features:
1. Add to Features table
2. Include SQL example
3. Update Quick Start if needed
4. Add to appropriate section

### Docstrings
```python
def function_name(param1: str) -> dict:
    """
    Brief description.
    
    Args:
        param1: Description of parameter
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this exception occurs
    """
```

## Performance Considerations

### Optimization Tips
1. **Use connection pooling**: Reuse DuckDB connections
2. **Batch operations**: Group SQL statements when possible
3. **Index appropriately**: Add indexes for frequently queried columns
4. **Lazy loading**: Load extensions only when needed
5. **Cache results**: Use DuckDB's caching mechanisms

### Memory Management
- Use `:memory:` database for temporary operations
- Clean up large result sets
- Monitor extension memory usage

## Security Best Practices

### Input Validation
- Sanitize user inputs before SQL execution
- Use parameterized queries
- Validate URLs before fetching

### Secrets Management
- Never hardcode secrets
- Use environment variables or secret stores
- Mock secrets in tests
- Use `get_secret()` macro pattern

### Dependency Security
- Keep dependencies updated
- Monitor security advisories
- Use `pip-audit` or similar tools
- Review extension code when possible

## MCP Memory Integration

### Persistent Context Storage
Use DuckDB tables to store agent context and memory:

```sql
-- Create memory table
CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id VARCHAR,
    context_key VARCHAR,
    context_value JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store context
INSERT INTO agent_memory (agent_id, context_key, context_value)
VALUES ('copilot', 'project_context', '{"language": "python", "framework": "duckdb"}')
ON CONFLICT (agent_id, context_key) DO UPDATE SET
    context_value = EXCLUDED.context_value,
    updated_at = CURRENT_TIMESTAMP;

-- Retrieve context
SELECT context_value FROM agent_memory 
WHERE agent_id = 'copilot' AND context_key = 'project_context';
```

### Context Types
- **project_context**: Project-wide settings and conventions
- **code_patterns**: Common code patterns and idioms
- **test_results**: Historical test results and coverage
- **deployment_history**: Deployment records and versions
- **issue_tracker**: Link to related issues and PRs

## CI/CD Integration

### GitHub Actions
Workflows in `.github/workflows/`:
- **CI**: Lint, test, and build on push/PR
- **Release**: Publish to PyPI on tag
- **Security**: Dependency scanning and CodeQL
- **Docker**: Build and push container images

### Workflow Triggers
```yaml
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  release:
    types: [published]
```

### Required Checks
1. Ruff linting passes
2. All tests pass
3. Docker build succeeds
4. No security vulnerabilities

## Troubleshooting

### Common Issues

#### Extension Load Failure
```python
# Solution: Try community extensions
try:
    con.sql("INSTALL extension_name FROM community;")
    con.sql("LOAD extension_name;")
except Exception as e:
    print(f"Extension unavailable: {e}")
```

#### MCP Server Won't Start
- Check DuckDB version compatibility
- Verify duckdb_mcp extension is loaded
- Check for port conflicts (though stdio shouldn't have this issue)

#### Macro Syntax Error
- Verify SQL syntax in DuckDB CLI first
- Check for missing semicolons
- Validate JSON structure in http_post body

## Contributing Workflow

1. **Fork and clone** repository
2. **Create feature branch**: `git checkout -b feature/description`
3. **Install dev dependencies**: `uv sync --dev`
4. **Make changes** following standards above
5. **Run linter**: `uv run ruff check --fix src/ tests/`
6. **Run tests**: `uv run pytest tests/`
7. **Commit** with descriptive message
8. **Push** to your fork
9. **Create PR** with clear description

## Questions to Ask

When implementing new features, consider:
- How does this integrate with existing macros?
- What DuckDB extensions are required?
- Does this need to be tested offline?
- Should this be documented in README?
- Are there security implications?
- What error cases should be handled?
- Does this affect the MCP protocol interface?

## Resources

### Documentation
- [DuckDB Documentation](https://duckdb.org/docs/)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [UV Package Manager](https://github.com/astral-sh/uv)

### Community
- Repository: https://github.com/bjoernbethge/agent-farm
- Issues: Report bugs and feature requests
- Discussions: Ask questions and share ideas

---

**Remember**: The goal of agent-farm is to make LLM agents more powerful through SQL-based tools and integrations. Every feature should enhance agent capabilities while maintaining simplicity and reliability.
