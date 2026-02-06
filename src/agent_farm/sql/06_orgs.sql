-- 06_orgs.sql - Organization management and inter-org communication

-- =============================================================================
-- ORG TABLES (if not created by main.py)
-- =============================================================================

CREATE TABLE IF NOT EXISTS orgs (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    org_type VARCHAR NOT NULL,
    description VARCHAR,
    model_primary VARCHAR NOT NULL,
    model_secondary VARCHAR,
    system_prompt TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS org_tools (
    org_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    requires_approval BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (org_id, tool_name)
);

CREATE TABLE IF NOT EXISTS org_denials (
    org_id VARCHAR NOT NULL,
    denial_type VARCHAR NOT NULL,
    pattern VARCHAR NOT NULL,
    reason VARCHAR,
    PRIMARY KEY (org_id, denial_type, pattern)
);

CREATE TABLE IF NOT EXISTS org_calls (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    caller_org VARCHAR NOT NULL,
    target_org VARCHAR NOT NULL,
    task VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    result JSON,
    created_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP
);

-- =============================================================================
-- ORG HELPER MACROS
-- =============================================================================

-- Get org system prompt
CREATE OR REPLACE MACRO get_org_prompt(org_id_param) AS (
    SELECT system_prompt FROM orgs WHERE id = org_id_param
);

-- Get org primary model
CREATE OR REPLACE MACRO get_org_model(org_id_param) AS (
    SELECT model_primary FROM orgs WHERE id = org_id_param
);

-- Check if tool is allowed for org
CREATE OR REPLACE MACRO is_org_tool_allowed(org_id_param, tool_name_param) AS (
    SELECT EXISTS (
        SELECT 1 FROM org_tools
        WHERE org_id = org_id_param
        AND tool_name = tool_name_param
        AND enabled = TRUE
    )
);

-- Check if tool requires approval for org
CREATE OR REPLACE MACRO org_tool_requires_approval(org_id_param, tool_name_param) AS (
    SELECT COALESCE(
        (SELECT requires_approval FROM org_tools
         WHERE org_id = org_id_param AND tool_name = tool_name_param),
        TRUE
    )
);

-- Check if action is denied for org
CREATE OR REPLACE MACRO is_org_action_denied(org_id_param, denial_type_param, check_pattern) AS (
    SELECT EXISTS (
        SELECT 1 FROM org_denials
        WHERE org_id = org_id_param
        AND denial_type = denial_type_param
        AND (check_pattern LIKE pattern OR pattern = '*')
    )
);

-- Get denial reason
CREATE OR REPLACE MACRO get_denial_reason(org_id_param, denial_type_param, check_pattern) AS (
    SELECT reason FROM org_denials
    WHERE org_id = org_id_param
    AND denial_type = denial_type_param
    AND (check_pattern LIKE pattern OR pattern = '*')
    LIMIT 1
);

-- =============================================================================
-- ORG POLICY ENFORCEMENT
-- =============================================================================

-- Check if org can execute tool
CREATE OR REPLACE MACRO org_can_execute(org_id_param, tool_name_param, tool_params) AS (
    SELECT CASE
        -- Tool not in org's allowed list
        WHEN NOT is_org_tool_allowed(org_id_param, tool_name_param)
            THEN json_object(
                'allowed', FALSE,
                'reason', 'Tool not allowed for this org: ' || tool_name_param
            )
        -- Tool is denied explicitly
        WHEN is_org_action_denied(org_id_param, 'tool', tool_name_param)
            THEN json_object(
                'allowed', FALSE,
                'reason', get_denial_reason(org_id_param, 'tool', tool_name_param)
            )
        -- Tool requires approval
        WHEN org_tool_requires_approval(org_id_param, tool_name_param)
            THEN json_object(
                'allowed', TRUE,
                'requires_approval', TRUE,
                'reason', 'Tool requires approval'
            )
        -- Tool allowed
        ELSE json_object('allowed', TRUE, 'requires_approval', FALSE)
    END
);

-- =============================================================================
-- ORCHESTRATOR ROUTING
-- =============================================================================

-- Log an org call
CREATE OR REPLACE MACRO log_org_call(session_id_param, caller_param, target_param, task_param) AS (
    SELECT json_object(
        'action', 'log_org_call',
        'session_id', session_id_param,
        'caller', caller_param,
        'target', target_param,
        'task', task_param,
        'note', 'Org call logging handled by Python runtime'
    )
);

-- Update org call result
CREATE OR REPLACE MACRO complete_org_call(call_id_param, result_json) AS (
    SELECT json_object(
        'action', 'complete_org_call',
        'call_id', call_id_param,
        'result', result_json,
        'note', 'Org call completion handled by Python runtime'
    )
);

-- Call another org (orchestrator function)
CREATE OR REPLACE MACRO call_org(caller_org_id, target_org_id, session_id_param, task_prompt) AS (
    WITH org_info AS (
        SELECT model_primary, system_prompt
        FROM orgs WHERE id = target_org_id
    )
    SELECT json_object(
        'target_org', target_org_id,
        'caller_org', caller_org_id,
        'model', org_info.model_primary,
        'task', task_prompt,
        'session_id', session_id_param,
        'status', 'dispatched'
    )
    FROM org_info
);

-- Orchestrator tools schema
CREATE OR REPLACE MACRO orchestrator_tools_schema() AS (
    SELECT json_array(
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'call_dev_org',
                'description', 'Calls DevOrg for code/pipeline tasks',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object(
                        'task', json_object('type', 'string', 'description', 'Task for DevOrg')
                    ),
                    'required', json_array('task')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'call_ops_org',
                'description', 'Calls OpsOrg for deployment/CI/CD tasks',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object(
                        'task', json_object('type', 'string', 'description', 'Task for OpsOrg')
                    ),
                    'required', json_array('task')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'call_research_org',
                'description', 'Calls ResearchOrg for research tasks',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object(
                        'task', json_object('type', 'string', 'description', 'Task for ResearchOrg')
                    ),
                    'required', json_array('task')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'call_studio_org',
                'description', 'Calls StudioOrg for specs/briefings',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object(
                        'task', json_object('type', 'string', 'description', 'Task for StudioOrg')
                    ),
                    'required', json_array('task')
                )
            )
        )
    )
);

-- Execute orchestrator tool call
CREATE OR REPLACE MACRO execute_orchestrator_tool(session_id_param, tool_name, tool_params) AS (
    SELECT CASE tool_name
        WHEN 'call_dev_org' THEN call_org(
            'orchestrator-org', 'dev-org', session_id_param,
            json_extract_string(tool_params, '$.task')
        )
        WHEN 'call_ops_org' THEN call_org(
            'orchestrator-org', 'ops-org', session_id_param,
            json_extract_string(tool_params, '$.task')
        )
        WHEN 'call_research_org' THEN call_org(
            'orchestrator-org', 'research-org', session_id_param,
            json_extract_string(tool_params, '$.task')
        )
        WHEN 'call_studio_org' THEN call_org(
            'orchestrator-org', 'studio-org', session_id_param,
            json_extract_string(tool_params, '$.task')
        )
        ELSE json_object('error', 'Unknown orchestrator tool', 'tool', tool_name)
    END
);

-- =============================================================================
-- ORG-SPECIFIC TOOL SCHEMAS
-- =============================================================================

-- DevOrg tools
CREATE OR REPLACE MACRO dev_org_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_read', 'description', 'Read file (only /projects/dev)',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string')), 'required', json_array('path'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_write', 'description', 'Write file (only /projects/dev)',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string'), 'content', json_object('type', 'string')),
                'required', json_array('path', 'content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_list', 'description', 'List directory',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string')), 'required', json_array('path'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'git_status', 'description', 'Show git status',
            'parameters', json_object('type', 'object', 'properties', json_object())
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'git_diff', 'description', 'Show git diff',
            'parameters', json_object('type', 'object', 'properties', json_object())
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'test_run', 'description', 'Run tests locally',
            'parameters', json_object('type', 'object', 'properties',
                json_object('test_path', json_object('type', 'string')), 'required', json_array('test_path'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'task_complete', 'description', 'Complete task',
            'parameters', json_object('type', 'object', 'properties',
                json_object('result', json_object('type', 'string')), 'required', json_array('result'))
        ))
    )
);

-- OpsOrg tools
CREATE OR REPLACE MACRO ops_org_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'ci_trigger', 'description', 'Trigger CI/CD pipeline',
            'parameters', json_object('type', 'object', 'properties',
                json_object('pipeline', json_object('type', 'string'), 'branch', json_object('type', 'string')),
                'required', json_array('pipeline'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'deploy_service', 'description', 'Deploy service (requires approval)',
            'parameters', json_object('type', 'object', 'properties',
                json_object('service', json_object('type', 'string'), 'environment', json_object('type', 'string')),
                'required', json_array('service', 'environment'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'rollback_service', 'description', 'Rollback service (requires approval)',
            'parameters', json_object('type', 'object', 'properties',
                json_object('service', json_object('type', 'string'), 'version', json_object('type', 'string')),
                'required', json_array('service', 'version'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'render_job_submit', 'description', 'Submit render job',
            'parameters', json_object('type', 'object', 'properties',
                json_object('job_config', json_object('type', 'string')), 'required', json_array('job_config'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'render_job_status', 'description', 'Get render job status',
            'parameters', json_object('type', 'object', 'properties',
                json_object('job_id', json_object('type', 'string')), 'required', json_array('job_id'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'task_complete', 'description', 'Complete task',
            'parameters', json_object('type', 'object', 'properties',
                json_object('result', json_object('type', 'string')), 'required', json_array('result'))
        ))
    )
);

-- ResearchOrg tools
CREATE OR REPLACE MACRO research_org_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'searxng_search', 'description', 'Web search via SearXNG',
            'parameters', json_object('type', 'object', 'properties',
                json_object('query', json_object('type', 'string'), 'categories', json_object('type', 'string')),
                'required', json_array('query'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_read', 'description', 'Read research note',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string')), 'required', json_array('path'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_write_note', 'description', 'Write research note',
            'parameters', json_object('type', 'object', 'properties',
                json_object('title', json_object('type', 'string'), 'content', json_object('type', 'string')),
                'required', json_array('title', 'content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_list_notes', 'description', 'List research notes',
            'parameters', json_object('type', 'object', 'properties', json_object())
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'task_complete', 'description', 'Complete task',
            'parameters', json_object('type', 'object', 'properties',
                json_object('result', json_object('type', 'string')), 'required', json_array('result'))
        ))
    )
);

-- StudioOrg tools
CREATE OR REPLACE MACRO studio_org_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_read', 'description', 'Read document',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string')), 'required', json_array('path'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'fs_write', 'description', 'Write document (only /projects/studio)',
            'parameters', json_object('type', 'object', 'properties',
                json_object('path', json_object('type', 'string'), 'content', json_object('type', 'string')),
                'required', json_array('path', 'content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'notes_board_create', 'description', 'Create note on board',
            'parameters', json_object('type', 'object', 'properties',
                json_object('project', json_object('type', 'string'), 'title', json_object('type', 'string'),
                    'content', json_object('type', 'string')),
                'required', json_array('project', 'title', 'content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'notes_board_list', 'description', 'List notes on board',
            'parameters', json_object('type', 'object', 'properties',
                json_object('project', json_object('type', 'string')), 'required', json_array('project'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'notes_board_update', 'description', 'Update note on board',
            'parameters', json_object('type', 'object', 'properties',
                json_object('note_id', json_object('type', 'string'), 'content', json_object('type', 'string')),
                'required', json_array('note_id', 'content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'task_complete', 'description', 'Complete task',
            'parameters', json_object('type', 'object', 'properties',
                json_object('result', json_object('type', 'string')), 'required', json_array('result'))
        ))
    )
);
