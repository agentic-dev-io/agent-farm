---
applyTo: "**/tests/**/*.py"
---

## Python Test Requirements

When writing or modifying Python tests in the agent-farm repository, follow these guidelines to ensure consistency and reliability:

### Test Framework & Structure

1. **Use pytest framework** - All tests should be compatible with pytest
2. **File naming** - Test files must follow the pattern `test_*.py` or `*_test.py`
3. **Function naming** - Test functions should start with `test_` prefix
4. **Docstrings** - Include clear docstrings describing what each test validates

### Testing DuckDB & SQL Macros

1. **In-memory databases** - Use `:memory:` connections for speed: `duckdb.connect(':memory:')`
2. **Extension loading** - Always handle extension loading errors gracefully:
   ```python
   try:
       con.sql("LOAD extension_name;")
   except Exception:
       pytest.skip("Extension not available")
   ```
3. **SQL statement parsing** - Use the existing `split_sql_statements()` helper from `tests/test_macros.py` for parsing SQL files
4. **Macro validation** - Test that macros can be created without syntax errors before testing functionality

### External Dependencies

1. **Mock HTTP requests** - Use mocking for any external HTTP calls to ensure tests are deterministic
2. **Avoid external services** - Don't make real calls to Ollama, DuckDuckGo, or other APIs in tests
3. **Environment isolation** - Tests should not depend on external environment or network connectivity

### Test Organization

1. **Setup/Teardown** - Use pytest fixtures for common setup, especially DuckDB connections
2. **Test independence** - Each test should be fully independent and not rely on other tests
3. **Cleanup** - Ensure connections are closed after tests to prevent resource leaks

### Assertions & Coverage

1. **Explicit assertions** - Use clear, specific assertions with descriptive messages
2. **Error cases** - Test both success and failure paths
3. **Edge cases** - Test NULL inputs, empty strings, invalid parameters
4. **Result validation** - Verify not just that code runs, but that results are correct

### Performance

1. **Fast execution** - Tests should complete quickly (< 1 second per test ideally)
2. **Minimal I/O** - Avoid file system operations where possible
3. **Parallel safety** - Tests should be safe to run in parallel with pytest-xdist

### Example Test Pattern

```python
def test_macro_name():
    """Test that macro_name works correctly with valid input."""
    con = duckdb.connect(':memory:')
    
    # Load required extensions
    try:
        con.sql("LOAD json;")
    except Exception:
        pytest.skip("json extension not available")
    
    # Create and test macro
    con.sql("CREATE MACRO test_macro(x) AS (SELECT x * 2);")
    result = con.sql("SELECT test_macro(5) as result;").fetchone()
    
    assert result[0] == 10, "Expected macro to double the input"
    con.close()
```

### Integration with CI

- All tests must pass before code can be merged
- Tests run on Python 3.11 and 3.12
- Run locally before pushing: `uv run pytest tests/ -v`
