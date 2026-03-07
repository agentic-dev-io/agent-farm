-- ollama.sql - Ollama and LLM integration macros

-- Base URL for Ollama API (overrideable via OLLAMA_BASE_URL env var)
CREATE OR REPLACE MACRO ollama_base() AS
    COALESCE(getenv('OLLAMA_BASE_URL'), 'http://localhost:11434');

-- Send a single prompt to an Ollama model and return the response text
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

-- Send a chat messages array (JSON) to an Ollama model and return raw response body
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

-- Ollama chat with tool definitions for function-calling support
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

-- DeepSeek v3 LLM via Ollama cloud
CREATE OR REPLACE MACRO deepseek(prompt) AS ollama_chat('deepseek-v3.2:cloud', prompt);
-- Kimi K2 LLM via Ollama cloud
CREATE OR REPLACE MACRO kimi(prompt) AS ollama_chat('kimi-k2.5:cloud', prompt);
-- Kimi K2 extended-thinking LLM via Ollama cloud
CREATE OR REPLACE MACRO kimi_think(prompt) AS ollama_chat('kimi-k2-thinking:cloud', prompt);
-- Gemini 3 Pro Preview via Ollama cloud
CREATE OR REPLACE MACRO gemini(prompt) AS ollama_chat('gemini-3-pro-preview:latest', prompt);
-- Gemini 3 Flash Preview (faster/cheaper) via Ollama cloud
CREATE OR REPLACE MACRO gemini_flash(prompt) AS ollama_chat('gemini-3-flash-preview:latest', prompt);
-- Qwen3 Coder — coding-focused model via Ollama cloud
CREATE OR REPLACE MACRO qwen3_coder(prompt) AS ollama_chat('qwen3-coder-next:cloud', prompt);
-- Qwen3 VL multimodal (vision-language) via Ollama cloud
CREATE OR REPLACE MACRO qwen3_vl(prompt) AS ollama_chat('qwen3-vl:235b-cloud', prompt);
-- Qwen 3.5 general-purpose LLM via Ollama cloud
CREATE OR REPLACE MACRO qwen(prompt) AS ollama_chat('qwen3.5:cloud', prompt);
-- GLM-5 LLM via Ollama cloud
CREATE OR REPLACE MACRO glm(prompt) AS ollama_chat('glm-5:cloud', prompt);
-- MiniMax M2.5 LLM via Ollama cloud
CREATE OR REPLACE MACRO minimax(prompt) AS ollama_chat('minimax-m2.5:cloud', prompt);
-- GPT OSS 120B large model via Ollama cloud
CREATE OR REPLACE MACRO gpt_oss(prompt) AS ollama_chat('gpt-oss:120b-cloud', prompt);
-- GPT OSS 20B fast model via Ollama cloud
CREATE OR REPLACE MACRO gpt_oss_small(prompt) AS ollama_chat('gpt-oss:20b-cloud', prompt);
-- GPT-5.3 Codex coding model via Ollama
CREATE OR REPLACE MACRO gpt_codex(prompt) AS ollama_chat('gpt-5.3-codex:latest', prompt);
-- Devstral 2 code agent model via Ollama cloud
CREATE OR REPLACE MACRO devstral(prompt) AS ollama_chat('devstral-2:123b-cloud', prompt);

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
