-- 07_org_tools.sql - Organization-specific tool implementations

-- =============================================================================
-- SEARXNG SEARCH (ResearchOrg)
-- =============================================================================

-- SearXNG endpoint (configurable)
CREATE OR REPLACE MACRO searxng_endpoint() AS
    COALESCE(getenv('SEARXNG_URL'), 'http://searxng:8080');

-- SearXNG search
CREATE OR REPLACE MACRO searxng_search(query, categories) AS (
    SELECT TRY(
        http_get(
            searxng_endpoint() || '/search?q=' || url_encode(query)
            || '&format=json'
            || CASE WHEN categories IS NOT NULL AND categories != ''
                THEN '&categories=' || url_encode(categories)
                ELSE ''
            END,
            headers := MAP {'Accept': 'application/json'}
        ).body::JSON
    )
);

-- SearXNG search simplified (just query)
CREATE OR REPLACE MACRO searxng(query) AS (
    searxng_search(query, NULL)
);

-- Extract search results
CREATE OR REPLACE MACRO searxng_results(query) AS (
    SELECT json_extract(searxng(query), '$.results')
);

-- =============================================================================
-- CI/CD TOOLS (OpsOrg)
-- =============================================================================

-- CI endpoint (configurable)
CREATE OR REPLACE MACRO ci_endpoint() AS
    COALESCE(getenv('CI_API_URL'), 'http://ci-server:8080/api');

-- CI API key
CREATE OR REPLACE MACRO ci_api_key() AS
    COALESCE(getenv('CI_API_KEY'), '');

-- Trigger CI pipeline
CREATE OR REPLACE MACRO ci_trigger(pipeline_name, branch_name) AS (
    SELECT TRY(
        http_post(
            ci_endpoint() || '/pipelines/' || url_encode(pipeline_name) || '/trigger',
            headers := MAP {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' || ci_api_key()
            },
            body := json_object(
                'ref', COALESCE(branch_name, 'main'),
                'triggered_by', 'agent-farm-ops'
            )
        ).body::JSON
    )
);

-- Get pipeline status
CREATE OR REPLACE MACRO ci_status(pipeline_id) AS (
    SELECT TRY(
        http_get(
            ci_endpoint() || '/pipelines/' || url_encode(pipeline_id),
            headers := MAP {'Authorization': 'Bearer ' || ci_api_key()}
        ).body::JSON
    )
);

-- =============================================================================
-- DEPLOYMENT TOOLS (OpsOrg)
-- =============================================================================

-- Deploy endpoint
CREATE OR REPLACE MACRO deploy_endpoint() AS
    COALESCE(getenv('DEPLOY_API_URL'), 'http://deploy-server:8080/api');

-- Deploy service (skeleton - returns approval_required for now)
CREATE OR REPLACE MACRO deploy_service(service_name, environment) AS (
    SELECT json_object(
        'status', 'approval_required',
        'service', service_name,
        'environment', environment,
        'message', 'Deployment benötigt manuelle Genehmigung',
        'action', 'deploy'
    )
);

-- Rollback service (skeleton - returns approval_required for now)
CREATE OR REPLACE MACRO rollback_service(service_name, target_version) AS (
    SELECT json_object(
        'status', 'approval_required',
        'service', service_name,
        'version', target_version,
        'message', 'Rollback benötigt manuelle Genehmigung',
        'action', 'rollback'
    )
);

-- =============================================================================
-- RENDER JOB TOOLS (OpsOrg)
-- =============================================================================

-- Render endpoint
CREATE OR REPLACE MACRO render_endpoint() AS
    COALESCE(getenv('RENDER_API_URL'), 'http://render-farm:8080/api');

-- Submit render job
CREATE OR REPLACE MACRO render_job_submit(job_config_json) AS (
    SELECT TRY(
        http_post(
            render_endpoint() || '/jobs',
            headers := MAP {'Content-Type': 'application/json'},
            body := job_config_json
        ).body::JSON
    )
);

-- Get render job status
CREATE OR REPLACE MACRO render_job_status(job_id) AS (
    SELECT TRY(
        http_get(render_endpoint() || '/jobs/' || url_encode(job_id)).body::JSON
    )
);

-- =============================================================================
-- NOTES BOARD (StudioOrg)
-- =============================================================================

-- Notes board table
CREATE TABLE IF NOT EXISTS notes_board (
    id VARCHAR PRIMARY KEY,
    project VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    content TEXT,
    note_type VARCHAR DEFAULT 'general',
    status VARCHAR DEFAULT 'open',
    created_by VARCHAR DEFAULT 'studio-org',
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Create note on board
CREATE OR REPLACE MACRO notes_board_create(project_name, note_title, note_content) AS (
    INSERT INTO notes_board (id, project, title, content)
    VALUES (
        'note-' || strftime(now(), '%Y%m%d%H%M%S') || '-' || (random() * 1000)::INTEGER,
        project_name,
        note_title,
        note_content
    )
    RETURNING json_object(
        'id', id,
        'project', project,
        'title', title,
        'status', 'created'
    )
);

-- List notes for project
CREATE OR REPLACE MACRO notes_board_list(project_name) AS (
    SELECT json_group_array(json_object(
        'id', id,
        'title', title,
        'status', status,
        'created_at', created_at::VARCHAR
    ))
    FROM notes_board
    WHERE project = project_name
    ORDER BY created_at DESC
);

-- Update note
CREATE OR REPLACE MACRO notes_board_update(note_id_param, new_content) AS (
    UPDATE notes_board
    SET content = new_content, updated_at = now()
    WHERE id = note_id_param
    RETURNING json_object(
        'id', id,
        'status', 'updated',
        'updated_at', updated_at::VARCHAR
    )
);

-- Get single note
CREATE OR REPLACE MACRO notes_board_get(note_id_param) AS (
    SELECT json_object(
        'id', id,
        'project', project,
        'title', title,
        'content', content,
        'status', status,
        'created_at', created_at::VARCHAR
    )
    FROM notes_board
    WHERE id = note_id_param
);

-- =============================================================================
-- RESEARCH NOTES (ResearchOrg)
-- =============================================================================

-- Research notes directory
CREATE OR REPLACE MACRO research_notes_dir() AS '/data/research';

-- Write research note (wrapper for fs_write with fixed path)
CREATE OR REPLACE MACRO fs_write_note(note_title, note_content) AS (
    SELECT json_object(
        'path', research_notes_dir() || '/' ||
            strftime(now(), '%Y%m%d') || '-' ||
            replace(lower(note_title), ' ', '-') || '.md',
        'title', note_title,
        'content_length', length(note_content),
        'status', 'written'
    )
);

-- List research notes
CREATE OR REPLACE MACRO fs_list_notes() AS (
    SELECT ls(research_notes_dir())
);

-- =============================================================================
-- TEST RUNNER (DevOrg)
-- =============================================================================

-- Run tests (uses pytest via shell, only in power mode)
CREATE OR REPLACE MACRO test_run(test_path) AS (
    SELECT CASE
        WHEN test_path NOT LIKE '/projects/dev%'
            THEN json_object('error', 'Tests nur in /projects/dev erlaubt')
        ELSE json_object(
            'command', 'pytest ' || test_path,
            'status', 'would_execute',
            'note', 'Shell-Ausführung benötigt approval oder power-mode'
        )
    END
);

-- =============================================================================
-- GIT PATCH (DevOrg)
-- =============================================================================

-- Create git patch
CREATE OR REPLACE MACRO git_patch(commit_range) AS (
    SELECT shell('git format-patch ' || COALESCE(commit_range, 'HEAD~1..HEAD') || ' --stdout')
);

-- Apply git patch (dry-run only)
CREATE OR REPLACE MACRO git_patch_check(patch_content) AS (
    SELECT json_object(
        'status', 'dry_run',
        'message', 'Patch-Anwendung benötigt Approval',
        'patch_size', length(patch_content)
    )
);

-- =============================================================================
-- ORG TOOL EXECUTOR
-- =============================================================================

-- Execute tool for specific org with policy checks
CREATE OR REPLACE MACRO execute_org_tool(org_id_param, session_id_param, tool_name, tool_params) AS (
    WITH policy_check AS (
        SELECT org_can_execute(org_id_param, tool_name, tool_params) as policy
    )
    SELECT CASE
        -- Policy denied
        WHEN NOT json_extract(policy_check.policy, '$.allowed')::BOOLEAN
            THEN json_object(
                'error', json_extract_string(policy_check.policy, '$.reason'),
                'tool', tool_name,
                'org', org_id_param
            )
        -- Requires approval
        WHEN json_extract(policy_check.policy, '$.requires_approval')::BOOLEAN
            THEN json_object(
                'status', 'approval_required',
                'tool', tool_name,
                'params', tool_params,
                'org', org_id_param
            )

        -- =========================================
        -- SMART EXTENSION TOOLS (09_smart_extensions.sql)
        -- =========================================

        -- JSONata Tools
        WHEN tool_name = 'json_transform'
            THEN json_transform(
                tool_params,
                json_extract_string(tool_params, '$.expression')
            )
        WHEN tool_name = 'research_parse_api'
            THEN research_parse_api(tool_params)
        WHEN tool_name = 'dev_validate_config'
            THEN dev_validate_config(
                tool_params,
                json_extract_string(tool_params, '$.required_fields')
            )

        -- DuckPGQ Tools (OrchestratorOrg)
        WHEN tool_name = 'orchestrator_call_chain'
            THEN orchestrator_call_chain(session_id_param)
        WHEN tool_name = 'orchestrator_add_dependency'
            THEN orchestrator_add_dependency(
                json_extract_string(tool_params, '$.task_id'),
                json_extract_string(tool_params, '$.depends_on'),
                json_extract_string(tool_params, '$.type')
            )
        WHEN tool_name = 'orchestrator_get_ready_tasks'
            THEN (SELECT json_group_array(json_object('id', id, 'task', task))
                  FROM orchestrator_get_ready_tasks())

        -- Bitfilters Tools (OpsOrg)
        WHEN tool_name = 'ops_is_duplicate'
            THEN ops_is_duplicate(
                json_extract_string(tool_params, '$.filter'),
                json_extract_string(tool_params, '$.entry')
            )::VARCHAR

        -- Lindel Tools (ResearchOrg + StudioOrg)
        WHEN tool_name = 'research_encode_embedding'
            THEN research_encode_embedding(
                json_extract(tool_params, '$.embedding')::DOUBLE[]
            )::VARCHAR
        WHEN tool_name = 'studio_index_asset'
            THEN studio_index_asset(
                json_extract_string(tool_params, '$.asset_id'),
                json_extract(tool_params, '$.features')::DOUBLE[]
            )
        WHEN tool_name = 'studio_find_similar'
            THEN (SELECT json_group_array(json_object(
                    'asset_id', asset_id,
                    'distance', distance
                  ))
                  FROM studio_find_similar(
                      json_extract(tool_params, '$.features')::DOUBLE[],
                      json_extract(tool_params, '$.limit')::INTEGER
                  ))

        -- LSH Tools (ResearchOrg)
        WHEN tool_name = 'research_index_doc'
            THEN research_index_doc(
                json_extract_string(tool_params, '$.doc_id'),
                json_extract_string(tool_params, '$.title'),
                json_extract_string(tool_params, '$.content')
            )
        WHEN tool_name = 'research_find_similar_docs'
            THEN (SELECT json_group_array(json_object(
                    'doc_id', doc_id,
                    'title', doc_title,
                    'similarity', similarity
                  ))
                  FROM research_find_similar_docs(
                      json_extract_string(tool_params, '$.content'),
                      json_extract(tool_params, '$.threshold')::DOUBLE,
                      json_extract(tool_params, '$.limit')::INTEGER
                  ))

        -- Radio Tools (Real-time)
        WHEN tool_name = 'orchestrator_broadcast'
            THEN orchestrator_broadcast(
                json_extract_string(tool_params, '$.channel'),
                tool_params
            )
        WHEN tool_name = 'orchestrator_listen'
            THEN orchestrator_listen(
                json_extract(tool_params, '$.timeout_ms')::INTEGER
            )
        WHEN tool_name = 'ops_publish_status'
            THEN ops_publish_status(
                json_extract_string(tool_params, '$.channel'),
                tool_params
            )
        WHEN tool_name = 'studio_collab_event'
            THEN studio_collab_event(
                json_extract_string(tool_params, '$.project'),
                json_extract_string(tool_params, '$.event_type'),
                tool_params
            )

        -- Smart Router (auto-detect best extension)
        WHEN tool_name = 'smart_route'
            THEN smart_route(
                org_id_param,
                json_extract_string(tool_params, '$.task_type'),
                tool_params
            )

        -- =========================================
        -- LEGACY ORG TOOLS
        -- =========================================

        -- SearXNG
        WHEN tool_name = 'searxng_search'
            THEN searxng_search(
                json_extract_string(tool_params, '$.query'),
                json_extract_string(tool_params, '$.categories')
            )
        -- CI/CD
        WHEN tool_name = 'ci_trigger'
            THEN ci_trigger(
                json_extract_string(tool_params, '$.pipeline'),
                json_extract_string(tool_params, '$.branch')
            )
        WHEN tool_name = 'deploy_service'
            THEN deploy_service(
                json_extract_string(tool_params, '$.service'),
                json_extract_string(tool_params, '$.environment')
            )
        WHEN tool_name = 'rollback_service'
            THEN rollback_service(
                json_extract_string(tool_params, '$.service'),
                json_extract_string(tool_params, '$.version')
            )
        -- Render
        WHEN tool_name = 'render_job_submit'
            THEN render_job_submit(json_extract_string(tool_params, '$.job_config'))
        WHEN tool_name = 'render_job_status'
            THEN render_job_status(json_extract_string(tool_params, '$.job_id'))
        -- Notes Board
        WHEN tool_name = 'notes_board_create'
            THEN notes_board_create(
                json_extract_string(tool_params, '$.project'),
                json_extract_string(tool_params, '$.title'),
                json_extract_string(tool_params, '$.content')
            )
        WHEN tool_name = 'notes_board_list'
            THEN notes_board_list(json_extract_string(tool_params, '$.project'))
        WHEN tool_name = 'notes_board_update'
            THEN notes_board_update(
                json_extract_string(tool_params, '$.note_id'),
                json_extract_string(tool_params, '$.content')
            )
        -- Research Notes
        WHEN tool_name = 'fs_write_note'
            THEN fs_write_note(
                json_extract_string(tool_params, '$.title'),
                json_extract_string(tool_params, '$.content')
            )
        WHEN tool_name = 'fs_list_notes'
            THEN fs_list_notes()
        -- Test
        WHEN tool_name = 'test_run'
            THEN test_run(json_extract_string(tool_params, '$.test_path'))
        -- Git
        WHEN tool_name = 'git_patch'
            THEN git_patch(json_extract_string(tool_params, '$.commit_range'))
        -- Fallback to standard tools
        ELSE execute_tool_safe(org_id_param, session_id_param, tool_name, tool_params)
    END
    FROM policy_check
);
