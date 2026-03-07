-- harness.sql - Agent harness, Anthropic + Ollama routing, tool execution

-- =============================================================================
-- ANTHROPIC API COMPATIBILITY
-- =============================================================================

CREATE OR REPLACE MACRO anthropic_base() AS
    COALESCE(getenv('ANTHROPIC_BASE_URL'), 'https://api.anthropic.com');

CREATE OR REPLACE MACRO anthropic_chat(model_name, messages_json, max_tokens) AS (
    SELECT http_post(
        anthropic_base() || '/v1/messages',
        headers := MAP {
            'Content-Type': 'application/json',
            'x-api-key': COALESCE(getenv('ANTHROPIC_API_KEY'), ''),
            'anthropic-version': '2023-06-01'
        },
        body := json_object(
            'model', model_name,
            'messages', json(messages_json),
            'max_tokens', max_tokens
        )
    ).body
);

CREATE OR REPLACE MACRO anthropic_chat_tools(model_name, messages_json, tools_json, max_tokens) AS (
    SELECT http_post(
        anthropic_base() || '/v1/messages',
        headers := MAP {
            'Content-Type': 'application/json',
            'x-api-key': COALESCE(getenv('ANTHROPIC_API_KEY'), ''),
            'anthropic-version': '2023-06-01'
        },
        body := json_object(
            'model', model_name,
            'messages', json(messages_json),
            'tools', json(tools_json),
            'max_tokens', max_tokens
        )
    ).body
);

-- Unified model call - routes to Ollama or Anthropic based on config
CREATE OR REPLACE MACRO model_call(agent_id_param, user_prompt, tools_json) AS (
    SELECT CASE
        WHEN (SELECT model_backend FROM agent_config WHERE id = agent_id_param) = 'claude_cloud'
        THEN anthropic_chat_tools(
            (SELECT model_name FROM agent_config WHERE id = agent_id_param),
            json_array(json_object('role', 'user', 'content', user_prompt)),
            tools_json,
            4096
        )
        ELSE ollama_chat_with_tools(
            (SELECT model_name FROM agent_config WHERE id = agent_id_param),
            json_array(json_object('role', 'user', 'content', user_prompt)),
            tools_json
        )
    END
);

-- =============================================================================
-- AGENT SYSTEM PROMPT
-- =============================================================================

CREATE OR REPLACE MACRO agent_system_prompt(agent_id_param) AS (
    SELECT
        'You are ' || name || ', a ' || role || ' assistant.' || chr(10) ||
        'Security Profile: ' || security_profile || chr(10) ||
        'Allowed Workspaces: ' || (
            SELECT string_agg(path, ', ')
            FROM workspaces WHERE agent_id = agent_id_param
        ) || chr(10) ||
        CASE WHEN (SELECT shell_enabled FROM security_policy WHERE agent_id = agent_id_param)
            THEN 'Shell: ENABLED (use with caution)'
            ELSE 'Shell: DISABLED'
        END || chr(10) ||
        'Rules: Only access allowed paths. Request approval for destructive operations.'
    FROM agent_config WHERE id = agent_id_param
);

CREATE OR REPLACE MACRO secure_agent_call(agent_id_param, model_name, user_prompt, tools_json) AS (
    SELECT agent_call(
        model_name,
        agent_system_prompt(agent_id_param),
        user_prompt,
        tools_json
    )
);

-- =============================================================================
-- TOOL SCHEMAS
-- =============================================================================

-- Legacy schema (without fs_write)
CREATE OR REPLACE MACRO local_tools_schema() AS (
    SELECT json_array(
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'fs_read',
                'description', 'Read file contents. Path must be in allowed workspace.',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('path', json_object('type', 'string', 'description', 'File path')),
                    'required', json_array('path')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'fs_list',
                'description', 'List directory contents. Path must be in allowed workspace.',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('path', json_object('type', 'string', 'description', 'Directory path')),
                    'required', json_array('path')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'shell_run',
                'description', 'Execute shell command. Only available in power profile.',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('cmd', json_object('type', 'string', 'description', 'Command to run')),
                    'required', json_array('cmd')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'web_search',
                'description', 'Search the web using DuckDuckGo.',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('query', json_object('type', 'string', 'description', 'Search query')),
                    'required', json_array('query')
                )
            )
        )
    )
);

-- Full agent tools schema including fs_write and task_complete
CREATE OR REPLACE MACRO agent_tools_schema() AS (
    SELECT json_array(
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'fs_read',
                'description', 'Read file contents from allowed workspace',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('path', json_object('type', 'string')),
                    'required', json_array('path')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'fs_write',
                'description', 'Write content to file in allowed workspace (requires writer/operator mode)',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object(
                        'path', json_object('type', 'string'),
                        'content', json_object('type', 'string')
                    ),
                    'required', json_array('path', 'content')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'fs_list',
                'description', 'List directory contents in allowed workspace',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('path', json_object('type', 'string')),
                    'required', json_array('path')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'shell_run',
                'description', 'Run shell command (power profile only, requires approval)',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('cmd', json_object('type', 'string')),
                    'required', json_array('cmd')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'web_search',
                'description', 'Search the web via DuckDuckGo',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('query', json_object('type', 'string')),
                    'required', json_array('query')
                )
            )
        ),
        json_object(
            'type', 'function',
            'function', json_object(
                'name', 'task_complete',
                'description', 'Mark task as complete with final response',
                'parameters', json_object(
                    'type', 'object',
                    'properties', json_object('result', json_object('type', 'string')),
                    'required', json_array('result')
                )
            )
        )
    )
);

-- =============================================================================
-- TOOL EXECUTION
-- =============================================================================

-- Legacy execute_tool (without approval check)
CREATE OR REPLACE MACRO execute_tool(agent_id_param, session_id_param, tool_name, tool_params) AS (
    SELECT CASE tool_name
        WHEN 'fs_read' THEN secure_read(agent_id_param, json_extract_string(tool_params, '$.path'))
        WHEN 'fs_list' THEN secure_ls(agent_id_param, json_extract_string(tool_params, '$.path'))
        WHEN 'shell_run' THEN secure_shell(agent_id_param, json_extract_string(tool_params, '$.cmd'))
        WHEN 'web_search' THEN json_object('results', ddg_instant(json_extract_string(tool_params, '$.query')))
        ELSE json_object('error', 'Unknown tool', 'tool', tool_name)
    END
);

-- Safe execute with approval check
CREATE OR REPLACE MACRO execute_tool_safe(agent_id_param, session_id_param, tool_name, tool_params) AS (
    SELECT CASE
        WHEN requires_approval(agent_id_param, tool_name, tool_params)
            THEN request_approval(
                session_id_param,
                tool_name,
                tool_params,
                'This action requires user approval'
            )
        WHEN tool_name = 'fs_read' THEN secure_read(agent_id_param, json_extract_string(tool_params, '$.path'))
        WHEN tool_name = 'fs_write' THEN secure_write(
            agent_id_param,
            json_extract_string(tool_params, '$.path'),
            json_extract_string(tool_params, '$.content')
        )
        WHEN tool_name = 'fs_list' THEN secure_ls(agent_id_param, json_extract_string(tool_params, '$.path'))
        WHEN tool_name = 'shell_run' THEN secure_shell(agent_id_param, json_extract_string(tool_params, '$.cmd'))
        WHEN tool_name = 'web_search' THEN json_object('results', ddg_instant(json_extract_string(tool_params, '$.query')))
        ELSE json_object('error', 'Unknown tool', 'tool', tool_name)
    END
);

CREATE OR REPLACE MACRO process_tool_call(agent_id_param, session_id_param, tool_call_json) AS (
    WITH tool_info AS (
        SELECT
            json_extract_string(tool_call_json, '$.function.name') as tool_name,
            json_extract_string(tool_call_json, '$.function.arguments') as tool_params
    )
    SELECT execute_tool_safe(agent_id_param, session_id_param, tool_name, tool_params)
    FROM tool_info
);

-- =============================================================================
-- AGENT LOOP / STEP
-- =============================================================================

-- Execute one step of agent loop
CREATE OR REPLACE MACRO agent_step(agent_id_param, session_id_param, messages_json) AS (
    WITH model_response AS (
        SELECT CASE
            WHEN (SELECT model_backend FROM agent_config WHERE id = agent_id_param) = 'claude_cloud'
            THEN anthropic_chat_tools(
                (SELECT model_name FROM agent_config WHERE id = agent_id_param),
                messages_json,
                agent_tools_schema(),
                4096
            )
            ELSE ollama_chat_with_tools(
                (SELECT model_name FROM agent_config WHERE id = agent_id_param),
                messages_json,
                agent_tools_schema()
            )
        END as response
    ),
    parsed AS (
        SELECT
            response,
            has_tool_calls(response) as has_tools,
            extract_tool_calls(response) as tool_calls,
            extract_response(response) as text_response
        FROM model_response
    )
    SELECT json_object(
        'status', CASE
            WHEN has_tools AND json_extract_string(tool_calls, '$[0].function.name') = 'task_complete' THEN 'complete'
            WHEN has_tools THEN 'continue'
            ELSE 'complete'
        END,
        'response', text_response,
        'tool_calls', tool_calls,
        'raw', response
    )
    FROM parsed
);

-- Quick one-shot agent call
CREATE OR REPLACE MACRO quick_agent(agent_id_param, user_prompt) AS (
    SELECT agent_step(
        agent_id_param,
        'quick-' || now()::VARCHAR,
        json_array(
            json_object('role', 'system', 'content', agent_system_prompt(agent_id_param)),
            json_object('role', 'user', 'content', user_prompt)
        )
    )
);
