-- macros.sql

-- Mock get_secret for now if not native:
CREATE OR REPLACE MACRO get_secret(name) AS 'mock_secret_value';

-- =============================================================================
-- OLLAMA BASE
-- =============================================================================

-- Base Ollama API endpoint
CREATE OR REPLACE MACRO ollama_base() AS 'http://localhost:11434';

-- Generic Ollama chat completion (simple)
CREATE OR REPLACE MACRO ollama_chat(model_name, prompt) AS (
    SELECT json_extract_string(
        http_post(
            ollama_base() || '/api/generate',
            headers := MAP {'Content-Type': 'application/json'},
            body := json_object(
                'model', model_name,
                'prompt', prompt,
                'stream', false
            )
        ).body,
        '$.response'
    )
);

-- Ollama chat with messages format (for tool calling)
CREATE OR REPLACE MACRO ollama_chat_messages(model_name, messages_json) AS (
    SELECT http_post(
        ollama_base() || '/api/chat',
        headers := MAP {'Content-Type': 'application/json'},
        body := json_object(
            'model', model_name,
            'messages', json(messages_json),
            'stream', false
        )
    ).body
);

-- Ollama chat WITH tools (function calling)
CREATE OR REPLACE MACRO ollama_chat_with_tools(model_name, messages_json, tools_json) AS (
    SELECT http_post(
        ollama_base() || '/api/chat',
        headers := MAP {'Content-Type': 'application/json'},
        body := json_object(
            'model', model_name,
            'messages', json(messages_json),
            'tools', json(tools_json),
            'stream', false
        )
    ).body
);

-- Extract tool calls from Ollama response
CREATE OR REPLACE MACRO extract_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls')
);

-- Extract text response from Ollama response
CREATE OR REPLACE MACRO extract_response(response_body) AS (
    SELECT json_extract_string(response_body, '$.message.content')
);

-- Ollama embeddings
CREATE OR REPLACE MACRO ollama_embed(model_name, text_input) AS (
    SELECT json_extract(
        http_post(
            ollama_base() || '/api/embeddings',
            headers := MAP {'Content-Type': 'application/json'},
            body := json_object(
                'model', model_name,
                'prompt', text_input
            )
        ).body,
        '$.embedding'
    )::FLOAT[]
);

-- =============================================================================
-- CLOUD MODELLE (via Ollama Gateway)
-- =============================================================================

-- DeepSeek V3.1 (671B Cloud)
CREATE OR REPLACE MACRO deepseek(prompt) AS ollama_chat('deepseek-v3.1:671b-cloud', prompt);

-- Kimi K2 (1T Cloud, mit Thinking-Variante)
CREATE OR REPLACE MACRO kimi(prompt) AS ollama_chat('kimi-k2:1t-cloud', prompt);
CREATE OR REPLACE MACRO kimi_think(prompt) AS ollama_chat('kimi-k2-thinking:cloud', prompt);

-- Gemini 3 Pro (Cloud)
CREATE OR REPLACE MACRO gemini(prompt) AS ollama_chat('gemini-3-pro-preview:latest', prompt);

-- Qwen3 Coder 480B (Cloud)
CREATE OR REPLACE MACRO qwen3_coder(prompt) AS ollama_chat('qwen3-coder:480b-cloud', prompt);

-- Qwen3 VL 235B (Vision, Cloud)
CREATE OR REPLACE MACRO qwen3_vl(prompt) AS ollama_chat('qwen3-vl:235b-cloud', prompt);

-- GLM 4.6 (Cloud)
CREATE OR REPLACE MACRO glm(prompt) AS ollama_chat('glm-4.6:cloud', prompt);

-- MiniMax M2 (Cloud)
CREATE OR REPLACE MACRO minimax(prompt) AS ollama_chat('minimax-m2:cloud', prompt);

-- GPT-OSS (Cloud, 120B und 20B)
CREATE OR REPLACE MACRO gpt_oss(prompt) AS ollama_chat('gpt-oss:120b-cloud', prompt);
CREATE OR REPLACE MACRO gpt_oss_small(prompt) AS ollama_chat('gpt-oss:20b-cloud', prompt);

-- =============================================================================
-- CLOUD MODELLE MIT TOOL CALLING
-- =============================================================================

-- DeepSeek with tools
CREATE OR REPLACE MACRO deepseek_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'deepseek-v3.1:671b-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

-- Kimi with tools
CREATE OR REPLACE MACRO kimi_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'kimi-k2:1t-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

-- Gemini with tools
CREATE OR REPLACE MACRO gemini_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'gemini-3-pro-preview:latest',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

-- Qwen3 Coder with tools
CREATE OR REPLACE MACRO qwen3_coder_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'qwen3-coder:480b-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

-- =============================================================================
-- MCP TOOL HELPERS
-- =============================================================================

-- Convert MCP tool schema to Ollama tool format
-- Usage: SELECT mcp_to_ollama_tool('tool_name', 'description', '{"type":"object","properties":{...}}')
CREATE OR REPLACE MACRO mcp_to_ollama_tool(tool_name, description, input_schema_json) AS (
    SELECT json_object(
        'type', 'function',
        'function', json_object(
            'name', tool_name,
            'description', description,
            'parameters', json(input_schema_json)
        )
    )
);

-- Build tools array from multiple tool definitions
CREATE OR REPLACE MACRO build_tools_array(tools_list) AS (
    SELECT json_group_array(json(tool)) FROM (SELECT unnest(tools_list) as tool)
);

-- =============================================================================
-- RAG HELPERS
-- =============================================================================

-- Standard RAG mit DeepSeek (beste Qualität)
CREATE OR REPLACE MACRO rag_query(question, context) AS
    deepseek('Beantworte basierend auf folgendem Kontext:\n\n' || context || '\n\nFrage: ' || question);

-- RAG mit Kimi Thinking (für komplexe Reasoning-Aufgaben)
CREATE OR REPLACE MACRO rag_think(question, context) AS
    kimi_think('Analysiere sorgfältig den Kontext und beantworte die Frage:\n\nKontext:\n' || context || '\n\nFrage: ' || question);

-- =============================================================================
-- AGENTIC HELPERS
-- =============================================================================

-- Agent loop: Send prompt with tools, get response
-- Returns full response including potential tool_calls
CREATE OR REPLACE MACRO agent_call(model_name, system_prompt, user_prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        model_name,
        json_array(
            json_object('role', 'system', 'content', system_prompt),
            json_object('role', 'user', 'content', user_prompt)
        ),
        tools_json
    )
);

-- Check if response contains tool calls
CREATE OR REPLACE MACRO has_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls') IS NOT NULL
        AND json_array_length(json_extract(response_body, '$.message.tool_calls')) > 0
);

-- =============================================================================
-- EXTERNAL APIS
-- =============================================================================

CREATE OR REPLACE MACRO elevenlabs_tts(text_input) AS TABLE
SELECT
    http_post(
        'https://api.elevenlabs.io/v1/tts/voice_id',
        headers := MAP {'xi-api-key': get_secret('elevenlabs_key')},
        body := json_object('text', text_input)
    ) AS audio_file_bytes;
