-- ============================================================================
-- Spec Engine HTTP Server Configuration
-- ============================================================================
-- Configuration for exposing the Spec Engine over HTTP using the httpserver
-- extension from Query.Farm.
--
-- Usage:
--   1. Set environment variables:
--      export SPEC_ENGINE_HTTP_PORT=9999
--      export SPEC_ENGINE_API_KEY=your-secret-key
--
--   2. Or start manually:
--      SELECT spec_http_start(9999, 'your-secret-key');
--
--   3. Query via curl:
--      curl -X POST \
--           -H "X-API-Key: your-secret-key" \
--           -d "SELECT * FROM spec_objects LIMIT 10" \
--           http://localhost:9999/
-- ============================================================================

-- ============================================================================
-- HTTP Server Management Views
-- ============================================================================

-- View for HTTP server status (when httpserver is loaded)
CREATE OR REPLACE VIEW http_server_info AS
SELECT
    'httpserver' AS component,
    'Query.Farm HTTP OLAP API' AS description,
    'Use SELECT httpserve_start() to start' AS hint;

-- ============================================================================
-- Convenience Endpoints (as views for common queries)
-- ============================================================================

-- GET /specs - List all active specs
CREATE OR REPLACE VIEW api_specs_list AS
SELECT id, kind, name, version, status, summary
FROM spec_objects
WHERE status = 'active'
ORDER BY kind, name;

-- GET /specs/agents - List all agents
CREATE OR REPLACE VIEW api_agents_list AS
SELECT
    o.id, o.name, o.version, o.status, o.summary,
    p.payload->>'role' AS role,
    p.payload->>'model' AS model
FROM spec_objects o
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'agent' AND o.status = 'active';

-- GET /specs/skills - List all skills
CREATE OR REPLACE VIEW api_skills_list AS
SELECT
    o.id, o.name, o.version, o.status, o.summary,
    json_array_length(p.payload->'tools') AS tool_count
FROM spec_objects o
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'skill' AND o.status = 'active';

-- GET /specs/templates - List all templates
CREATE OR REPLACE VIEW api_templates_list AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary
FROM spec_objects o
WHERE o.kind IN ('task_template', 'prompt_template')
  AND o.status = 'active';

-- GET /stats - Spec Engine statistics
CREATE OR REPLACE VIEW api_stats AS
SELECT
    kind,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'active') AS active,
    COUNT(*) FILTER (WHERE status = 'draft') AS draft,
    COUNT(*) FILTER (WHERE status = 'deprecated') AS deprecated
FROM spec_objects
GROUP BY kind
ORDER BY kind;

-- ============================================================================
-- Example HTTP Requests
-- ============================================================================

-- The following are example curl commands for the HTTP API:
--
-- List all specs:
--   curl -X POST -H "X-API-Key: $API_KEY" \
--        -d "SELECT * FROM api_specs_list" \
--        http://localhost:9999/
--
-- Get a specific spec:
--   curl -X POST -H "X-API-Key: $API_KEY" \
--        -d "SELECT * FROM spec_full_view WHERE name = 'pia'" \
--        http://localhost:9999/
--
-- Search specs:
--   curl -X POST -H "X-API-Key: $API_KEY" \
--        -d "SELECT * FROM spec_search('planner')" \
--        http://localhost:9999/
--
-- Render a template:
--   curl -X POST -H "X-API-Key: $API_KEY" \
--        -d "SELECT spec_render_template('plan_pia_swarm', '{\"task_name\": \"Test\", \"objective\": \"Testing\", \"steps\": [], \"success_criteria\": []}')" \
--        http://localhost:9999/
--
-- Get statistics:
--   curl -X POST -H "X-API-Key: $API_KEY" \
--        -d "SELECT * FROM api_stats" \
--        http://localhost:9999/
