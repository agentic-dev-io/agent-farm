---
applyTo: "**/*.sql"
---

## SQL Macro Development Guidelines

When creating or modifying DuckDB SQL macros in the agent-farm repository, follow these standards for consistency, maintainability, and reliability:

### Macro Structure

1. **Use CREATE OR REPLACE** - Always use `CREATE OR REPLACE MACRO` to allow reloading without errors
2. **Documentation comments** - Add clear comments above each macro explaining its purpose and parameters
3. **Parameter documentation** - Document each parameter with type and purpose in comments
4. **Consistent naming** - Use `snake_case` for all macro names (e.g., `ollama_chat`, `ddg_search`)

### Syntax Standards

1. **Parentheses** - Always wrap macro body in parentheses: `AS (SELECT ...)`
2. **Semicolons** - End each CREATE statement with a semicolon
3. **Formatting** - Use consistent indentation (2 or 4 spaces)
4. **Line breaks** - Break long queries into readable lines

### Error Handling

1. **NULL safety** - Handle NULL inputs gracefully with COALESCE or NULL checks
2. **TRY() function** - Wrap error-prone operations in TRY() to prevent crashes and return NULL on errors:
   ```sql
   SELECT TRY(CAST('invalid' AS INTEGER))  -- Returns NULL instead of error
   ```
3. **Default values** - Provide sensible defaults for optional parameters
4. **Validation** - Validate inputs before processing when possible

### HTTP & External Calls

1. **http_post/http_get** - Use the http_client extension functions consistently
2. **Headers** - Always specify Content-Type for POST requests: `headers := MAP {'Content-Type': 'application/json'}`
3. **Body construction** - Use `json_object()` for constructing JSON payloads
4. **Response parsing** - Use `json_extract_string()` or similar for parsing responses
5. **Error responses** - Handle HTTP errors and return meaningful results

### Performance Considerations

1. **Minimize nesting** - Avoid deeply nested SELECT statements
2. **Use CTEs** - Use Common Table Expressions for complex queries to improve readability
3. **Avoid redundant calls** - Cache results when making expensive operations
4. **Lazy evaluation** - Design macros to only execute what's necessary

### LLM Integration Patterns

1. **Model parameters** - Accept model name as first parameter
2. **Prompt parameter** - Use clear parameter names like `prompt` or `query`
3. **Stream handling** - Default to `stream: false` for synchronous responses
4. **Response extraction** - Extract only the relevant response field (e.g., `$.response` or `$.choices[0].message.content`)

### Example Macro Template

```sql
-- Description: Brief description of what this macro does
-- Parameters:
--   param1: Description of first parameter (TYPE)
--   param2: Description of second parameter (TYPE)
-- Returns: Description of return value
CREATE OR REPLACE MACRO macro_name(param1, param2 := 'default') AS (
    SELECT TRY(
        json_extract_string(
            http_post(
                'https://api.example.com/endpoint',
                headers := MAP {'Content-Type': 'application/json'},
                body := json_object(
                    'key1', COALESCE(param1, ''),
                    'key2', param2
                )
            ).body,
            '$.result'
        )
    )
);
```

### Common Macro Patterns

#### Simple HTTP GET
```sql
CREATE OR REPLACE MACRO fetch(url) AS (
    SELECT http_get(url).body
);
```

#### LLM Call with JSON Response
```sql
CREATE OR REPLACE MACRO llm_query(model, prompt) AS (
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

#### Shell Command Execution (when shellfs available)
```sql
CREATE OR REPLACE MACRO shell(cmd) AS (
    SELECT read_text(format('shell://{0}', cmd))
);
```

### Testing Macros

1. **Syntax validation** - Ensure macro can be created without errors
2. **Basic functionality** - Test with typical inputs
3. **Edge cases** - Test with NULL, empty strings, special characters
4. **Error conditions** - Verify graceful handling of errors

### Integration with Extensions

- **Required extensions**: Document which DuckDB extensions the macro requires
- **Graceful degradation**: Where possible, provide fallback behavior if optional extensions aren't available
- **Extension loading**: Assume extensions are loaded by main.py, don't load within macros

### Documentation Requirements

When adding new macros to `macros.sql`:
1. Update README.md with usage example
2. Add to appropriate feature category
3. Include expected input/output format
4. Mention any required extensions or external dependencies (Ollama, APIs, etc.)
