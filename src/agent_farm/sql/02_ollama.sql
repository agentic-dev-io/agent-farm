-- 02_ollama.sql - Ollama and LLM integration macros

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

-- Cloud models via Ollama Gateway
CREATE OR REPLACE MACRO deepseek(prompt) AS ollama_chat('deepseek-v3.1:671b-cloud', prompt);
CREATE OR REPLACE MACRO kimi(prompt) AS ollama_chat('kimi-k2:1t-cloud', prompt);
CREATE OR REPLACE MACRO kimi_think(prompt) AS ollama_chat('kimi-k2-thinking:cloud', prompt);
CREATE OR REPLACE MACRO gemini(prompt) AS ollama_chat('gemini-3-pro-preview:latest', prompt);
CREATE OR REPLACE MACRO qwen3_coder(prompt) AS ollama_chat('qwen3-coder:480b-cloud', prompt);
CREATE OR REPLACE MACRO qwen3_vl(prompt) AS ollama_chat('qwen3-vl:235b-cloud', prompt);
CREATE OR REPLACE MACRO glm(prompt) AS ollama_chat('glm-4.6:cloud', prompt);
CREATE OR REPLACE MACRO minimax(prompt) AS ollama_chat('minimax-m2:cloud', prompt);
CREATE OR REPLACE MACRO gpt_oss(prompt) AS ollama_chat('gpt-oss:120b-cloud', prompt);
CREATE OR REPLACE MACRO gpt_oss_small(prompt) AS ollama_chat('gpt-oss:20b-cloud', prompt);

-- Cloud models with tool calling
CREATE OR REPLACE MACRO deepseek_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'deepseek-v3.1:671b-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

CREATE OR REPLACE MACRO kimi_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'kimi-k2:1t-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

CREATE OR REPLACE MACRO gemini_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'gemini-3-pro-preview:latest',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

CREATE OR REPLACE MACRO qwen3_coder_tools(prompt, tools_json) AS (
    SELECT ollama_chat_with_tools(
        'qwen3-coder:480b-cloud',
        json_array(json_object('role', 'user', 'content', prompt)),
        tools_json
    )
);

-- MCP tool helpers
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

CREATE OR REPLACE MACRO build_tools_array(tools_list) AS (
    SELECT json_group_array(json(tool)) FROM (SELECT unnest(tools_list) as tool)
);

-- Agentic helpers
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

CREATE OR REPLACE MACRO has_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls') IS NOT NULL
        AND json_array_length(json_extract(response_body, '$.message.tool_calls')) > 0
);

-- Vector/Embedding helpers
CREATE OR REPLACE MACRO cosine_sim(vec1, vec2) AS (
    list_cosine_similarity(vec1, vec2)
);

CREATE OR REPLACE MACRO embed(text_input) AS (
    ollama_embed('nomic-embed-text', text_input)
);

CREATE OR REPLACE MACRO semantic_score(query_text, doc_text) AS (
    cosine_sim(embed(query_text), embed(doc_text))
);

-- RAG helpers
CREATE OR REPLACE MACRO rag_query(question, context) AS
    deepseek('Answer based on the following context:\n\n' || context || '\n\nQuestion: ' || question);

CREATE OR REPLACE MACRO rag_think(question, context) AS
    kimi_think('Carefully analyze the context and answer the question:\n\nContext:\n' || context || '\n\nQuestion: ' || question);
