---
name: SQL Macro Request
about: Request a new SQL macro for agent-farm
title: '[MACRO] '
labels: enhancement, sql-macro
assignees: ''
---

## Macro Name
<!-- Proposed name for the macro -->

`macro_name()`

## Purpose
<!-- What does this macro do? -->

## Parameters
<!-- List the parameters the macro should accept -->

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `param1` | VARCHAR | | Yes |
| `param2` | INTEGER | | No |

## Expected Output
<!-- What should the macro return? -->

**Return Type**: [VARCHAR, JSON, TABLE, etc.]

## Example Usage
```sql
-- Example of how the macro would be used
SELECT macro_name('input', 123);
```

## Expected Result
```
-- Example output
```

## Integration Requirements
<!-- What DuckDB extensions or external services are needed? -->

- [ ] DuckDB Extensions: 
- [ ] External APIs: 
- [ ] Authentication required: 

## Similar Functionality
<!-- Are there existing macros with similar functionality? -->

## Implementation Approach
<!-- Optional: suggest how this could be implemented -->

```sql
-- Rough implementation idea
CREATE OR REPLACE MACRO macro_name(param1, param2) AS (
    -- implementation
);
```

## Use Cases
<!-- Describe specific use cases for this macro -->

1. 
2. 

## Additional Context
<!-- Add any other context, examples, or references -->
