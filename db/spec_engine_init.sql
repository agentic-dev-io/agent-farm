-- ============================================================================
-- Spec Engine Initialization SQL
-- ============================================================================
-- This file loads all required DuckDB extensions for the Spec Engine.
-- Extensions: minijinja, json_schema, duckdb_mcp, httpserver
-- ============================================================================

-- Install extensions from community repository
INSTALL minijinja FROM community;
INSTALL json_schema FROM community;
INSTALL duckdb_mcp FROM community;
INSTALL httpserver FROM community;

-- Also install commonly used extensions for full functionality
INSTALL json;
INSTALL httpfs;
INSTALL http_client FROM community;

-- Load all extensions
LOAD minijinja;
LOAD json_schema;
LOAD duckdb_mcp;
LOAD httpserver;
LOAD json;
LOAD httpfs;
LOAD http_client;

-- Verify extensions are loaded
SELECT extension_name, loaded, installed
FROM duckdb_extensions()
WHERE extension_name IN ('minijinja', 'json_schema', 'duckdb_mcp', 'httpserver', 'json', 'httpfs', 'http_client')
ORDER BY extension_name;
