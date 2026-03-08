-- ollama.sql - Ollama and LLM integration macros

-- Base URL for Ollama API (overrideable via OLLAMA_BASE_URL env var)
CREATE OR REPLACE MACRO ollama_base() AS
    COALESCE(getenv('OLLAMA_BASE_URL'), 'http://localhost:11434');

-- Ollama chat with tool definitions (only path; use empty json_array() for no tools)
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

-- Extract tool_calls array from an Ollama chat response body
CREATE OR REPLACE MACRO extract_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls')
);

-- Extract text content from an Ollama chat response body
CREATE OR REPLACE MACRO extract_response(response_body) AS (
    SELECT json_extract_string(response_body, '$.message.content')
);

-- Generate a float embedding vector for text using an Ollama embedding model
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

-- Model shortcuts: single prompt via chat-with-tools (empty tools), return text
CREATE OR REPLACE MACRO deepseek(prompt) AS extract_response(ollama_chat_with_tools('deepseek-v3.2:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO kimi(prompt) AS extract_response(ollama_chat_with_tools('kimi-k2.5:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO kimi_think(prompt) AS extract_response(ollama_chat_with_tools('kimi-k2-thinking:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO gemini(prompt) AS extract_response(ollama_chat_with_tools('gemini-3-pro-preview:latest', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO gemini_flash(prompt) AS extract_response(ollama_chat_with_tools('gemini-3-flash-preview:latest', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO qwen3_coder(prompt) AS extract_response(ollama_chat_with_tools('qwen3-coder-next:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO qwen3_vl(prompt) AS extract_response(ollama_chat_with_tools('qwen3-vl:235b-cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO qwen(prompt) AS extract_response(ollama_chat_with_tools('qwen3.5:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO glm(prompt) AS extract_response(ollama_chat_with_tools('glm-5:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO minimax(prompt) AS extract_response(ollama_chat_with_tools('minimax-m2.5:cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO gpt_oss(prompt) AS extract_response(ollama_chat_with_tools('gpt-oss:120b-cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO gpt_oss_small(prompt) AS extract_response(ollama_chat_with_tools('gpt-oss:20b-cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO gpt_codex(prompt) AS extract_response(ollama_chat_with_tools('gpt-5.3-codex:latest', json_array(json_object('role', 'user', 'content', prompt)), json_array()));
CREATE OR REPLACE MACRO devstral(prompt) AS extract_response(ollama_chat_with_tools('devstral-2:123b-cloud', json_array(json_object('role', 'user', 'content', prompt)), json_array()));

-- Single-turn agent call: build system+user messages and invoke model with tools
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

-- Return true if an Ollama response body contains tool calls
CREATE OR REPLACE MACRO has_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls') IS NOT NULL
        AND json_array_length(json_extract(response_body, '$.message.tool_calls')) > 0
);

-- Cosine similarity between two float embedding vectors
CREATE OR REPLACE MACRO cosine_sim(vec1, vec2) AS (
    list_cosine_similarity(vec1, vec2)
);

-- Embed text using nomic-embed-text model via Ollama
CREATE OR REPLACE MACRO embed(text_input) AS (
    ollama_embed('nomic-embed-text', text_input)
);

-- Semantic similarity score between two texts (0–1) via embeddings
CREATE OR REPLACE MACRO semantic_score(query_text, doc_text) AS (
    cosine_sim(embed(query_text), embed(doc_text))
);

-- RAG query: answer a question from a given context using DeepSeek
CREATE OR REPLACE MACRO rag_query(question, context) AS
    deepseek('Answer based on the following context:\n\n' || context || '\n\nQuestion: ' || question);

-- RAG query with extended thinking via Kimi for complex analysis
CREATE OR REPLACE MACRO rag_think(question, context) AS
    kimi_think('Carefully analyze the context and answer the question:\n\nContext:\n' || context || '\n\nQuestion: ' || question);
