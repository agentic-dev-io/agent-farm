-- ============================================================================
-- Spec Engine SQL Macros
-- ============================================================================
-- Macros for template rendering (MiniJinja), JSON Schema validation,
-- and MCP integration (duckdb_mcp).
-- ============================================================================

-- ============================================================================
-- A) Template Rendering Macros (MiniJinja)
-- ============================================================================

-- Render a template by name with a JSON context
-- Usage: SELECT spec_render_template('plan_pia_swarm', '{"agent_name": "Pia"}');
CREATE OR REPLACE MACRO spec_render_template(template_name, context) AS (
    SELECT minijinja_render(
        (
            SELECT p.payload->>'template'
            FROM spec_objects o
            JOIN spec_payloads p ON p.object_id = o.id
            WHERE o.kind IN ('task_template', 'prompt_template')
              AND o.name = template_name
              AND o.status = 'active'
            ORDER BY o.version DESC
            LIMIT 1
        ),
        context
    )
);

-- Render a template with version specification
-- Usage: SELECT spec_render_template_v('plan_pia_swarm', '1.0.0', '{"agent_name": "Pia"}');
CREATE OR REPLACE MACRO spec_render_template_v(template_name, version, context) AS (
    SELECT minijinja_render(
        (
            SELECT p.payload->>'template'
            FROM spec_objects o
            JOIN spec_payloads p ON p.object_id = o.id
            WHERE o.kind IN ('task_template', 'prompt_template')
              AND o.name = template_name
              AND o.version = version
            LIMIT 1
        ),
        context
    )
);

-- Direct template rendering (without DB lookup)
-- Usage: SELECT spec_render('Hello {{ name }}!', '{"name": "World"}');
CREATE OR REPLACE MACRO spec_render(template_str, context) AS (
    SELECT minijinja_render(template_str, context)
);

-- Get raw template string by name
-- Usage: SELECT spec_get_template('plan_pia_swarm');
CREATE OR REPLACE MACRO spec_get_template(template_name) AS (
    SELECT p.payload->>'template'
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind IN ('task_template', 'prompt_template')
      AND o.name = template_name
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- ============================================================================
-- B) JSON Schema Validation Macros
-- ============================================================================

-- Validate a payload against a named schema spec
-- Usage: SELECT spec_validate('agent_config_schema', '{"name": "test"}');
CREATE OR REPLACE MACRO spec_validate(schema_name, payload) AS (
    SELECT json_schema_validate(
        (
            SELECT p.payload
            FROM spec_objects o
            JOIN spec_payloads p ON p.object_id = o.id
            WHERE o.kind = 'schema'
              AND o.name = schema_name
              AND o.status = 'active'
            ORDER BY o.version DESC
            LIMIT 1
        ),
        payload
    )
);

-- Validate a payload against a spec's associated schema_ref
-- Usage: SELECT spec_validate_against('agent', 'pia', '{"role": "planner"}');
CREATE OR REPLACE MACRO spec_validate_against(spec_kind, spec_name, payload) AS (
    WITH spec_info AS (
        SELECT p.schema_ref
        FROM spec_objects o
        JOIN spec_payloads p ON p.object_id = o.id
        WHERE o.kind = spec_kind
          AND o.name = spec_name
          AND o.status = 'active'
        ORDER BY o.version DESC
        LIMIT 1
    ),
    schema_payload AS (
        SELECT sp.payload AS schema_json
        FROM spec_objects so
        JOIN spec_payloads sp ON sp.object_id = so.id
        WHERE so.kind = 'schema'
          AND so.name = (SELECT schema_ref FROM spec_info)
          AND so.status = 'active'
        LIMIT 1
    )
    SELECT json_schema_validate(
        (SELECT schema_json FROM schema_payload),
        payload
    )
);

-- Check if payload is valid (returns boolean)
-- Usage: SELECT spec_is_valid('agent_config_schema', '{"name": "test"}');
CREATE OR REPLACE MACRO spec_is_valid(schema_name, payload) AS (
    SELECT CASE
        WHEN spec_validate(schema_name, payload) IS NULL THEN true
        WHEN spec_validate(schema_name, payload) = '' THEN true
        ELSE false
    END
);

-- ============================================================================
-- C) Spec Query Macros
-- ============================================================================

-- List specs by kind
-- Usage: SELECT * FROM spec_list_by_kind('agent');
CREATE OR REPLACE MACRO spec_list_by_kind(kind_filter) AS TABLE (
    SELECT id, kind, name, version, status, summary, created_at
    FROM spec_objects
    WHERE kind = kind_filter
    ORDER BY name, version DESC
);

-- List all active specs
-- Usage: SELECT * FROM spec_list_active();
CREATE OR REPLACE MACRO spec_list_active() AS TABLE (
    SELECT id, kind, name, version, status, summary, created_at
    FROM spec_objects
    WHERE status = 'active'
    ORDER BY kind, name
);

-- Search specs by name or summary (case-insensitive)
-- Usage: SELECT * FROM spec_search('pia');
CREATE OR REPLACE MACRO spec_search(query) AS TABLE (
    SELECT id, kind, name, version, status, summary
    FROM spec_objects
    WHERE LOWER(name) LIKE '%' || LOWER(query) || '%'
       OR LOWER(summary) LIKE '%' || LOWER(query) || '%'
    ORDER BY
        CASE WHEN LOWER(name) LIKE LOWER(query) || '%' THEN 0 ELSE 1 END,
        name
);

-- Search specs with doc content
-- Usage: SELECT * FROM spec_search_full('planner');
CREATE OR REPLACE MACRO spec_search_full(query) AS TABLE (
    SELECT DISTINCT o.id, o.kind, o.name, o.version, o.status, o.summary
    FROM spec_objects o
    LEFT JOIN spec_docs d ON d.object_id = o.id
    WHERE LOWER(o.name) LIKE '%' || LOWER(query) || '%'
       OR LOWER(o.summary) LIKE '%' || LOWER(query) || '%'
       OR LOWER(d.doc) LIKE '%' || LOWER(query) || '%'
    ORDER BY o.kind, o.name
);

-- Get a single spec by ID
-- Usage: SELECT * FROM spec_get_by_id(1);
CREATE OR REPLACE MACRO spec_get_by_id(spec_id) AS TABLE (
    SELECT
        o.id, o.kind, o.name, o.version, o.status, o.summary,
        o.created_at, o.updated_at,
        d.doc,
        p.payload,
        p.schema_ref
    FROM spec_objects o
    LEFT JOIN spec_docs d ON d.object_id = o.id
    LEFT JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.id = spec_id
);

-- Get a spec by kind and name (latest version)
-- Usage: SELECT * FROM spec_get('agent', 'pia');
CREATE OR REPLACE MACRO spec_get(kind_filter, name_filter) AS TABLE (
    SELECT
        o.id, o.kind, o.name, o.version, o.status, o.summary,
        o.created_at, o.updated_at,
        d.doc,
        p.payload,
        p.schema_ref
    FROM spec_objects o
    LEFT JOIN spec_docs d ON d.object_id = o.id
    LEFT JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = kind_filter
      AND o.name = name_filter
    ORDER BY o.version DESC
    LIMIT 1
);

-- Get a spec by kind, name, and version
-- Usage: SELECT * FROM spec_get_v('agent', 'pia', '1.0.0');
CREATE OR REPLACE MACRO spec_get_v(kind_filter, name_filter, version_filter) AS TABLE (
    SELECT
        o.id, o.kind, o.name, o.version, o.status, o.summary,
        o.created_at, o.updated_at,
        d.doc,
        p.payload,
        p.schema_ref
    FROM spec_objects o
    LEFT JOIN spec_docs d ON d.object_id = o.id
    LEFT JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = kind_filter
      AND o.name = name_filter
      AND o.version = version_filter
);

-- Get spec payload JSON
-- Usage: SELECT spec_get_payload('agent', 'pia');
CREATE OR REPLACE MACRO spec_get_payload(kind_filter, name_filter) AS (
    SELECT p.payload
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = kind_filter
      AND o.name = name_filter
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- Get spec documentation
-- Usage: SELECT spec_get_doc('agent', 'pia');
CREATE OR REPLACE MACRO spec_get_doc(kind_filter, name_filter) AS (
    SELECT d.doc
    FROM spec_objects o
    JOIN spec_docs d ON d.object_id = o.id
    WHERE o.kind = kind_filter
      AND o.name = name_filter
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- ============================================================================
-- D) Spec Mutation Macros (for internal use)
-- ============================================================================

-- Insert a new spec object (returns the ID)
-- Note: These are helper macros; actual inserts should use sequences
CREATE OR REPLACE MACRO spec_insert_object(
    kind_val, name_val, version_val, status_val, summary_val
) AS (
    SELECT nextval('spec_objects_seq') AS new_id
);

-- ============================================================================
-- E) MCP Integration Macros (duckdb_mcp)
-- ============================================================================

-- List resources from a remote MCP server
-- Usage: SELECT * FROM mcp_list_remote('server_name');
CREATE OR REPLACE MACRO mcp_list_remote(server_name) AS TABLE (
    SELECT * FROM mcp_list_resources(server_name)
);

-- List tools from a remote MCP server
-- Usage: SELECT * FROM mcp_list_tools_remote('server_name');
CREATE OR REPLACE MACRO mcp_list_tools_remote(server_name) AS TABLE (
    SELECT * FROM mcp_list_tools(server_name)
);

-- List prompts from a remote MCP server
-- Usage: SELECT * FROM mcp_list_prompts_remote('server_name');
CREATE OR REPLACE MACRO mcp_list_prompts_remote(server_name) AS TABLE (
    SELECT * FROM mcp_list_prompts(server_name)
);

-- Call a remote MCP tool
-- Usage: SELECT mcp_call_remote_tool('server_name', 'tool_name', '{"arg": "value"}');
CREATE OR REPLACE MACRO mcp_call_remote_tool(server_name, tool_name, args) AS (
    SELECT mcp_call_tool(server_name, tool_name, args)
);

-- Get a resource from a remote MCP server
-- Usage: SELECT mcp_get_remote_resource('server_name', 'resource_uri');
CREATE OR REPLACE MACRO mcp_get_remote_resource(server_name, resource_uri) AS (
    SELECT mcp_get_resource(server_name, resource_uri)
);

-- Get a prompt from a remote MCP server
-- Usage: SELECT mcp_get_remote_prompt('server_name', 'prompt_name', '{"arg": "value"}');
CREATE OR REPLACE MACRO mcp_get_remote_prompt(server_name, prompt_name, args) AS (
    SELECT mcp_get_prompt(server_name, prompt_name, args)
);

-- ============================================================================
-- F) Agent/Org Helper Macros
-- ============================================================================

-- Get agent system prompt from spec
-- Usage: SELECT spec_agent_prompt('pia');
CREATE OR REPLACE MACRO spec_agent_prompt(agent_name) AS (
    SELECT p.payload->>'system_prompt'
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = 'agent'
      AND o.name = agent_name
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- Get agent model configuration
-- Usage: SELECT spec_agent_model('pia');
CREATE OR REPLACE MACRO spec_agent_model(agent_name) AS (
    SELECT p.payload->>'model'
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = 'agent'
      AND o.name = agent_name
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- Get skill tools schema
-- Usage: SELECT spec_skill_tools('duckdb-spec-engine');
CREATE OR REPLACE MACRO spec_skill_tools(skill_name) AS (
    SELECT p.payload->'tools'
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = 'skill'
      AND o.name = skill_name
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- Get workflow steps
-- Usage: SELECT spec_workflow_steps('agent_onboarding');
CREATE OR REPLACE MACRO spec_workflow_steps(workflow_name) AS (
    SELECT p.payload->'steps'
    FROM spec_objects o
    JOIN spec_payloads p ON p.object_id = o.id
    WHERE o.kind = 'workflow'
      AND o.name = workflow_name
      AND o.status = 'active'
    ORDER BY o.version DESC
    LIMIT 1
);

-- ============================================================================
-- G) HTTP Server Helpers (httpserver extension)
-- ============================================================================

-- Start HTTP server for Spec Engine API
-- Usage: SELECT spec_http_start(9999, 'my-secret-token');
CREATE OR REPLACE MACRO spec_http_start(port, api_key) AS (
    SELECT httpserve_start('0.0.0.0', port, 'X-API-Key ' || api_key)
);

-- Stop HTTP server
-- Usage: SELECT spec_http_stop();
CREATE OR REPLACE MACRO spec_http_stop() AS (
    SELECT httpserve_stop()
);

-- ============================================================================
-- H) Statistics and Metadata Macros
-- ============================================================================

-- Get spec counts by kind
-- Usage: SELECT * FROM spec_stats();
CREATE OR REPLACE MACRO spec_stats() AS TABLE (
    SELECT
        kind,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status = 'active') AS active,
        COUNT(*) FILTER (WHERE status = 'draft') AS draft,
        COUNT(*) FILTER (WHERE status = 'deprecated') AS deprecated
    FROM spec_objects
    GROUP BY kind
    ORDER BY kind
);

-- Get all spec kinds in use
-- Usage: SELECT * FROM spec_kinds();
CREATE OR REPLACE MACRO spec_kinds() AS TABLE (
    SELECT DISTINCT kind
    FROM spec_objects
    ORDER BY kind
);

-- Get recently updated specs
-- Usage: SELECT * FROM spec_recent(10);
CREATE OR REPLACE MACRO spec_recent(limit_count) AS TABLE (
    SELECT id, kind, name, version, status, summary, updated_at
    FROM spec_objects
    ORDER BY updated_at DESC
    LIMIT limit_count
);

-- ============================================================================
-- I) Self-Learning / Meta-Learning Query Macros
-- ============================================================================
-- NOTE: Mutation operations (INSERT/UPDATE) should be done via the Python API
-- (SpecEngine.record_feedback, record_usage, record_adaptation, etc.)
-- These macros are for querying learning data only.

-- Get specs related to a given spec
-- Usage: SELECT * FROM spec_related_to(10);
CREATE OR REPLACE MACRO spec_related_to(spec_id_val) AS TABLE (
    SELECT
        r.rel_type,
        o.id, o.kind, o.name, o.version, o.status, o.summary
    FROM spec_relationships r
    JOIN spec_objects o ON o.id = r.to_id
    WHERE r.from_id = spec_id_val
    UNION ALL
    SELECT
        r.rel_type || '_by' AS rel_type,
        o.id, o.kind, o.name, o.version, o.status, o.summary
    FROM spec_relationships r
    JOIN spec_objects o ON o.id = r.from_id
    WHERE r.to_id = spec_id_val
);

-- Get performance metrics for a spec
-- Usage: SELECT * FROM spec_performance(10);
CREATE OR REPLACE MACRO spec_performance(spec_id_val) AS TABLE (
    SELECT
        o.id, o.kind, o.name,
        o.use_count,
        o.success_rate,
        o.confidence,
        COUNT(f.id) AS feedback_count,
        AVG(f.score) AS avg_score,
        COUNT(a.id) AS adaptation_count
    FROM spec_objects o
    LEFT JOIN spec_feedback f ON f.spec_id = o.id
    LEFT JOIN spec_adaptations a ON a.spec_id = o.id
    WHERE o.id = spec_id_val
    GROUP BY o.id, o.kind, o.name, o.use_count, o.success_rate, o.confidence
);

-- Get low-performing specs that need improvement
-- Usage: SELECT * FROM spec_needs_improvement(0.5, 5);
CREATE OR REPLACE MACRO spec_needs_improvement(min_usage, max_success_rate) AS TABLE (
    SELECT
        id, kind, name, version, status,
        use_count, success_rate, confidence,
        summary
    FROM spec_objects
    WHERE use_count >= min_usage
      AND success_rate < max_success_rate
      AND status = 'active'
    ORDER BY success_rate ASC, use_count DESC
);

-- Get specs that need sync with upstream
-- Usage: SELECT * FROM spec_needs_sync();
CREATE OR REPLACE MACRO spec_needs_sync() AS TABLE (
    SELECT
        id, kind, name, version,
        source_type, source_url, upstream_version,
        last_sync, sync_status,
        summary
    FROM spec_objects
    WHERE source_type = 'upstream'
      AND sync_status IN ('outdated', 'conflict')
    ORDER BY last_sync ASC NULLS FIRST
);

-- Get top learnings by confidence
-- Usage: SELECT * FROM spec_top_learnings(10);
CREATE OR REPLACE MACRO spec_top_learnings(limit_count) AS TABLE (
    SELECT
        id, learning_type, category,
        description, confidence,
        application,
        created_at
    FROM spec_learning
    WHERE confidence >= 0.5
    ORDER BY confidence DESC, created_at DESC
    LIMIT limit_count
);

-- ============================================================================
-- J) Provenance Query Macros
-- ============================================================================
-- NOTE: Provenance mutations should be done via the Python API
-- (SpecEngine.set_upstream_source, etc.)

-- Get upstream specs grouped by source
-- Usage: SELECT * FROM spec_upstream_sources();
CREATE OR REPLACE MACRO spec_upstream_sources() AS TABLE (
    SELECT
        source_url,
        COUNT(*) AS spec_count,
        MAX(last_sync) AS last_synced,
        array_agg(name) AS spec_names
    FROM spec_objects
    WHERE source_type = 'upstream'
    GROUP BY source_url
    ORDER BY last_synced ASC
);

-- Get learned specs by confidence
-- Usage: SELECT * FROM spec_learned_by_confidence(0.7);
CREATE OR REPLACE MACRO spec_learned_by_confidence(min_confidence) AS TABLE (
    SELECT
        id, kind, name, version,
        confidence, use_count, success_rate,
        summary
    FROM spec_objects
    WHERE source_type = 'learned'
      AND confidence >= min_confidence
    ORDER BY confidence DESC
);
