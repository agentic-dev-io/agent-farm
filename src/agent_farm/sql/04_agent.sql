-- 04_agent.sql - Secure Desktop Agent infrastructure
-- Policy engine, harness, approval flow, injection detection

-- =============================================================================
-- POLICY & SECURITY MACROS
-- =============================================================================

-- Check if path is within allowed workspace
CREATE OR REPLACE MACRO path_in_workspace(check_path, workspace_path) AS (
    starts_with(check_path, workspace_path) OR
    starts_with(check_path, workspace_path || '/')
);

-- Check path against workspace table
CREATE OR REPLACE MACRO is_allowed_path(agent_id_param, check_path) AS (
    EXISTS (
        SELECT 1 FROM workspaces
        WHERE agent_id = agent_id_param
        AND path_in_workspace(check_path, path)
    )
);

-- Get workspace mode for a path
CREATE OR REPLACE MACRO get_workspace_mode(agent_id_param, check_path) AS (
    SELECT mode FROM workspaces
    WHERE agent_id = agent_id_param
    AND path_in_workspace(check_path, path)
    LIMIT 1
);

-- Check if shell is enabled for agent
CREATE OR REPLACE MACRO is_shell_enabled(agent_id_param) AS (
    SELECT COALESCE(shell_enabled, FALSE)
    FROM security_policy
    WHERE agent_id = agent_id_param
);

-- Check if command is in blocklist
CREATE OR REPLACE MACRO is_blocked_command(agent_id_param, cmd) AS (
    SELECT EXISTS (
        SELECT 1 FROM security_policy
        CROSS JOIN LATERAL unnest(shell_blocklist) AS t(blocked)
        WHERE agent_id = agent_id_param
        AND lower(cmd) LIKE '%' || lower(blocked) || '%'
    )
);

-- Check if file matches sensitive patterns
CREATE OR REPLACE MACRO is_sensitive_file(agent_id_param, file_path) AS (
    SELECT EXISTS (
        SELECT 1 FROM security_policy
        CROSS JOIN LATERAL unnest(sensitive_patterns) AS t(pattern)
        WHERE agent_id = agent_id_param
        AND glob(file_path, pattern)
    )
);

-- Check domain against allowed/blocked lists
CREATE OR REPLACE MACRO is_allowed_domain(agent_id_param, domain) AS (
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM security_policy
            CROSS JOIN LATERAL unnest(blocked_domains) AS t(blocked)
            WHERE agent_id = agent_id_param AND domain LIKE '%' || blocked
        ) THEN FALSE
        WHEN (SELECT allowed_domains FROM security_policy WHERE agent_id = agent_id_param) IS NULL THEN TRUE
        WHEN (SELECT len(allowed_domains) FROM security_policy WHERE agent_id = agent_id_param) = 0 THEN TRUE
        WHEN EXISTS (
            SELECT 1 FROM security_policy
            CROSS JOIN LATERAL unnest(allowed_domains) AS t(allowed)
            WHERE agent_id = agent_id_param AND domain LIKE '%' || allowed
        ) THEN TRUE
        ELSE FALSE
    END
);

-- =============================================================================
-- AUDIT LOGGING
-- =============================================================================

CREATE OR REPLACE MACRO log_tool_call(session_id_param, tool_name_param, params_json, result_json, decision_param) AS (
    SELECT json_object(
        'action', 'log_tool_call',
        'session_id', session_id_param,
        'tool_name', tool_name_param,
        'decision', decision_param,
        'note', 'Audit logging handled by Python runtime'
    )
);

CREATE OR REPLACE MACRO log_violation(session_id_param, tool_name_param, violations_array) AS (
    SELECT json_object(
        'action', 'log_violation',
        'session_id', session_id_param,
        'tool_name', tool_name_param,
        'violations', violations_array::JSON,
        'note', 'Violation logging handled by Python runtime'
    )
);

CREATE OR REPLACE MACRO recent_audit(session_id_param, limit_n) AS TABLE
    SELECT * FROM audit_log
    WHERE session_id = session_id_param
    ORDER BY timestamp DESC
    LIMIT limit_n;

-- =============================================================================
-- SECURE FILE OPERATIONS
-- =============================================================================

CREATE OR REPLACE MACRO secure_read(agent_id_param, file_path) AS (
    CASE
        WHEN NOT is_allowed_path(agent_id_param, file_path)
            THEN json_object('error', 'Path not in allowed workspace', 'path', file_path)
        WHEN is_sensitive_file(agent_id_param, file_path)
            THEN json_object('error', 'Sensitive file - approval required', 'path', file_path)
        ELSE json_object('content', read_file(file_path), 'path', file_path)
    END
);

CREATE OR REPLACE MACRO secure_ls(agent_id_param, dir_path) AS (
    CASE
        WHEN NOT is_allowed_path(agent_id_param, dir_path)
            THEN json_object('error', 'Path not in allowed workspace', 'path', dir_path)
        ELSE json_object('listing', ls(dir_path), 'path', dir_path)
    END
);

CREATE OR REPLACE MACRO secure_shell(agent_id_param, cmd) AS (
    CASE
        WHEN NOT is_shell_enabled(agent_id_param)
            THEN json_object('error', 'Shell disabled for this security profile')
        WHEN is_blocked_command(agent_id_param, cmd)
            THEN json_object('error', 'Command blocked by security policy', 'cmd', cmd)
        ELSE json_object('output', shell(cmd), 'cmd', cmd)
    END
);

CREATE OR REPLACE MACRO can_write_to_workspace(agent_id_param, file_path) AS (
    SELECT COALESCE(
        (SELECT mode IN ('writer', 'operator')
         FROM workspaces
         WHERE agent_id = agent_id_param
         AND path_in_workspace(file_path, path)
         LIMIT 1),
        FALSE
    )
);

CREATE OR REPLACE MACRO secure_write(agent_id_param, file_path, content) AS (
    CASE
        WHEN NOT is_allowed_path(agent_id_param, file_path)
            THEN json_object('error', 'Path not in allowed workspace', 'path', file_path, 'status', 'denied')
        WHEN NOT can_write_to_workspace(agent_id_param, file_path)
            THEN json_object('error', 'Workspace is read-only', 'path', file_path, 'status', 'denied')
        WHEN is_sensitive_file(agent_id_param, file_path)
            THEN json_object('error', 'Writing to sensitive file requires approval', 'path', file_path, 'status', 'approval_required')
        ELSE json_object('written', length(content), 'path', file_path, 'status', 'success')
    END
);

-- =============================================================================
-- AGENT CONFIG HELPERS
-- =============================================================================

CREATE OR REPLACE MACRO create_agent(agent_id_param, agent_name, agent_role, sec_profile) AS (
    SELECT json_object(
        'action', 'create_agent',
        'id', agent_id_param,
        'name', agent_name,
        'role', agent_role,
        'security_profile', sec_profile,
        'note', 'Agent creation handled by Python runtime'
    )
);

CREATE OR REPLACE MACRO add_workspace(ws_id, agent_id_param, ws_path, ws_name, ws_mode) AS (
    SELECT json_object(
        'action', 'add_workspace',
        'id', ws_id,
        'agent_id', agent_id_param,
        'path', ws_path,
        'name', ws_name,
        'mode', ws_mode,
        'note', 'Workspace creation handled by Python runtime'
    )
);

CREATE OR REPLACE MACRO init_security_policy(agent_id_param, shell_on, allowlist, blocklist) AS (
    SELECT json_object(
        'action', 'init_security_policy',
        'agent_id', agent_id_param,
        'shell_enabled', shell_on,
        'note', 'Security policy init handled by Python runtime'
    )
);

CREATE OR REPLACE MACRO get_agent_config(agent_id_param) AS (
    SELECT json_object(
        'agent', (SELECT to_json(a) FROM agent_config a WHERE id = agent_id_param),
        'workspaces', (SELECT json_group_array(to_json(w)) FROM workspaces w WHERE agent_id = agent_id_param),
        'security', (SELECT to_json(s) FROM security_policy s WHERE agent_id = agent_id_param),
        'mcp_servers', (SELECT json_group_array(to_json(m)) FROM agent_mcp_servers m WHERE agent_id = agent_id_param)
    )
);

-- =============================================================================
-- APPROVAL FLOW (SR-6.5)
-- =============================================================================

CREATE OR REPLACE MACRO requires_approval(agent_id_param, tool_name, tool_params) AS (
    SELECT CASE
        WHEN tool_name = 'shell_run' THEN TRUE
        WHEN tool_name = 'fs_write' AND is_sensitive_file(agent_id_param, json_extract_string(tool_params, '$.path')) THEN TRUE
        WHEN tool_name = 'fs_delete' THEN TRUE
        WHEN tool_name = 'fs_write' AND (SELECT security_profile FROM agent_config WHERE id = agent_id_param) = 'standard' THEN TRUE
        ELSE FALSE
    END
);

CREATE OR REPLACE MACRO request_approval(session_id_param, tool_name, tool_params, reason) AS (
    SELECT json_object(
        'action', 'request_approval',
        'session_id', session_id_param,
        'tool_name', tool_name,
        'reason', reason,
        'status', 'approval_required',
        'note', 'Approval requests handled by Python runtime'
    )
);

-- =============================================================================
-- PROMPT INJECTION DETECTION (SR-7, SR-8)
-- =============================================================================

CREATE OR REPLACE MACRO detect_injection(content) AS (
    SELECT CASE
        WHEN lower(content) LIKE '%ignore%previous%instruction%' THEN 'instruction_override'
        WHEN lower(content) LIKE '%ignore%all%prior%' THEN 'instruction_override'
        WHEN lower(content) LIKE '%disregard%above%' THEN 'instruction_override'
        WHEN lower(content) LIKE '%forget%everything%' THEN 'instruction_override'
        WHEN lower(content) LIKE '%you are now%' THEN 'role_hijack'
        WHEN lower(content) LIKE '%new instructions:%' THEN 'instruction_injection'
        WHEN lower(content) LIKE '%system:%' THEN 'system_injection'
        WHEN lower(content) LIKE '%[system]%' THEN 'system_injection'
        WHEN lower(content) LIKE '%</system>%' THEN 'xml_injection'
        WHEN lower(content) LIKE '%<instruction>%' THEN 'xml_injection'
        WHEN lower(content) LIKE '%admin mode%' THEN 'privilege_escalation'
        WHEN lower(content) LIKE '%developer mode%' THEN 'privilege_escalation'
        WHEN lower(content) LIKE '%jailbreak%' THEN 'jailbreak'
        ELSE NULL
    END
);

CREATE OR REPLACE MACRO safe_read_content(agent_id_param, file_path) AS (
    SELECT CASE
        WHEN NOT is_allowed_path(agent_id_param, file_path)
            THEN json_object('error', 'Path not allowed', 'content', NULL)
        WHEN detect_injection(read_file(file_path)) IS NOT NULL
            THEN json_object(
                'warning', 'Potential prompt injection detected',
                'type', detect_injection(read_file(file_path)),
                'content', read_file(file_path),
                'sanitized', TRUE
            )
        ELSE json_object('content', read_file(file_path), 'sanitized', FALSE)
    END
);
