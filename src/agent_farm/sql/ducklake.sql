-- =============================================================================
-- DuckLake shared catalog macros (READ operations only)
-- =============================================================================
-- Architecture: `lake` DuckLake catalog attached by bootstrap_db when ducklake
-- extension is loaded. Cross-process persistent tables:
--   lake.notes_board        -- project notes shared across REPL + MCP sessions
--   lake.shared_sessions    -- agent sessions visible to all processes
--   lake.shared_org_calls   -- inter-org calls persisted in DuckLake
--
-- DML (INSERT/UPDATE): run directly on lake.* tables:
--   INSERT INTO lake.notes_board (id, project, title, content) VALUES (...);
--   UPDATE lake.notes_board SET content = '...' WHERE id = 'xyz';
--
-- DuckLake = SQLite metadata catalog + Parquet data files (lake_data/).
-- Concurrent attach: multiple DuckDB processes share the same catalog (MVCC).
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Notes board queries
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_notes() AS TABLE
    SELECT id, project, title, content, note_type, status, created_by, created_at, updated_at
    FROM lake.notes_board
    ORDER BY updated_at DESC;


CREATE OR REPLACE MACRO lake_notes_by_project(project_name) AS TABLE
    SELECT id, title, content, note_type, status, created_by, created_at, updated_at
    FROM lake.notes_board
    WHERE project = project_name
    ORDER BY updated_at DESC;


CREATE OR REPLACE MACRO lake_notes_open() AS TABLE
    SELECT id, project, title, content, note_type, created_by, created_at
    FROM lake.notes_board
    WHERE status = 'open'
    ORDER BY created_at DESC;


-- ---------------------------------------------------------------------------
-- Shared session queries
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_sessions() AS TABLE
    SELECT id, agent_id, process_type, started_at, status, context
    FROM lake.shared_sessions
    ORDER BY started_at DESC;


CREATE OR REPLACE MACRO lake_sessions_active() AS TABLE
    SELECT id, agent_id, process_type, started_at, context
    FROM lake.shared_sessions
    WHERE status = 'active'
    ORDER BY started_at DESC;


-- ---------------------------------------------------------------------------
-- Shared org call queries
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_org_calls() AS TABLE
    SELECT id, session_id, caller_org, target_org, task, status, created_at, completed_at
    FROM lake.shared_org_calls
    ORDER BY created_at DESC;


CREATE OR REPLACE MACRO lake_org_calls_pending() AS TABLE
    SELECT id, session_id, caller_org, target_org, task, created_at
    FROM lake.shared_org_calls
    WHERE status = 'pending'
    ORDER BY created_at ASC;


-- ---------------------------------------------------------------------------
-- DuckLake time-travel and storage macros (use TABLE functions in FROM)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_snapshots(tbl) AS TABLE
    SELECT * FROM ducklake_snapshots('lake', tbl) ORDER BY snapshot_id DESC;


CREATE OR REPLACE MACRO lake_files(tbl) AS TABLE
    SELECT * FROM ducklake_list_files('lake', tbl);


CREATE OR REPLACE MACRO lake_table_info(tbl) AS TABLE
    SELECT * FROM ducklake_table_info('lake', tbl);


-- ---------------------------------------------------------------------------
-- App instance queries (cross-session HTML renders)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_app_instances() AS TABLE
    SELECT instance_id, app_id, session_id, status, created_at, completed_at
    FROM lake.mcp_app_instances
    ORDER BY created_at DESC;

CREATE OR REPLACE MACRO lake_app_instance_html(instance_id_param) AS TABLE
    SELECT rendered_html
    FROM lake.mcp_app_instances
    WHERE instance_id = instance_id_param
    ORDER BY created_at DESC
    LIMIT 1;


-- ---------------------------------------------------------------------------
-- Approval queries (persistent across MCP restarts)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_approvals_pending() AS TABLE
    SELECT id, session_id, tool_name, tool_params, reason, created_at
    FROM lake.pending_approvals
    WHERE status = 'pending'
    ORDER BY created_at ASC;

CREATE OR REPLACE MACRO lake_approvals_all() AS TABLE
    SELECT id, session_id, tool_name, status, decision, resolved_by, created_at, resolved_at
    FROM lake.pending_approvals
    ORDER BY created_at DESC;


-- ---------------------------------------------------------------------------
-- User profile queries
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_user_profile(user_id_param) AS TABLE
    SELECT user_id, profile_id, custom_settings, created_at, updated_at
    FROM lake.user_profile
    WHERE user_id = user_id_param;


-- ---------------------------------------------------------------------------
-- DuckLake health / status overview
-- ---------------------------------------------------------------------------

CREATE OR REPLACE MACRO lake_status() AS TABLE
    SELECT 'notes_board'      AS table_name,
           count(*)           AS row_count,
           max(updated_at)    AS last_change
    FROM lake.notes_board
    UNION ALL
    SELECT 'shared_sessions', count(*), max(started_at)
    FROM lake.shared_sessions
    UNION ALL
    SELECT 'shared_org_calls', count(*), max(created_at)
    FROM lake.shared_org_calls
    UNION ALL
    SELECT 'mcp_app_instances', count(*), max(created_at)
    FROM lake.mcp_app_instances
    UNION ALL
    SELECT 'pending_approvals', count(*), max(created_at)
    FROM lake.pending_approvals
    UNION ALL
    SELECT 'user_profile', count(*), max(updated_at)
    FROM lake.user_profile;