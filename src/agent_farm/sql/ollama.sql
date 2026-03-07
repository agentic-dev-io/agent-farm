-- ollama.sql - Ollama and LLM integration macros

CREATE OR REPLACE MACRO ollama_base() AS 'http://localhost:11434';

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

CREATE OR REPLACE MACRO extract_tool_calls(response_body) AS (
    SELECT json_extract(response_body, '$.message.tool_calls')
);

CREATE OR REPLACE MACRO extract_response(response_body) AS (
    SELECT json_extract_string(response_body, '$.message.content')
);

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

CREATE OR REPLACE MACRO deepseek(prompt) AS ollama_chat('deepseek-v3.2:cloud', prompt);
CREATE OR REPLACE MACRO kimi(prompt) AS ollama_chat('kimi-k2.5:cloud', prompt);
CREATE OR REPLACE MACRO kimi_think(prompt) AS ollama_chat('kimi-k2-thinking:cloud', prompt);
CREATE OR REPLACE MACRO gemini(prompt) AS ollama_chat('gemini-3-pro-preview:latest', prompt);
CREATE OR REPLACE MACRO gemini_flash(prompt) AS ollama_chat('gemini-3-flash-preview:latest', prompt);
CREATE OR REPLACE MACRO qwen3_coder(prompt) AS ollama_chat('qwen3-coder-next:cloud', prompt);
CREATE OR REPLACE MACRO qwen3_vl(prompt) AS ollama_chat('qwen3-vl:235b-cloud', prompt);
CREATE OR REPLACE MACRO qwen(prompt) AS ollama_chat('qwen3.5:cloud', prompt);
CREATE OR REPLACE MACRO glm(prompt) AS ollama_chat('glm-5:cloud', prompt);
CREATE OR REPLACE MACRO minimax(prompt) AS ollama_chat('minimax-m2.5:cloud', prompt);
CREATE OR REPLACE MACRO gpt_oss(prompt) AS ollama_chat('gpt-oss:120b-cloud', prompt);
CREATE OR REPLACE MACRO gpt_oss_small(prompt) AS ollama_chat('gpt-oss:20b-cloud', prompt);
CREATE OR REPLACE MACRO gpt_codex(prompt) AS ollama_chat('gpt-5.3-codex:latest', prompt);
CREATE OR REPLACE MACRO devstral(prompt) AS ollama_chat('devstral-2:123b-cloud', prompt);

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

CREATE OR REPLACE MACRO cosine_sim(vec1, vec2) AS (
    list_cosine_similarity(vec1, vec2)
);

CREATE OR REPLACE MACRO embed(text_input) AS (
    ollama_embed('nomic-embed-text', text_input)
);

CREATE OR REPLACE MACRO semantic_score(query_text, doc_text) AS (
    cosine_sim(embed(query_text), embed(doc_text))
);

CREATE OR REPLACE MACRO rag_query(question, context) AS
    deepseek('Answer based on the following context:\n\n' || context || '\n\nQuestion: ' || question);

CREATE OR REPLACE MACRO rag_think(question, context) AS
    kimi_think('Carefully analyze the context and answer the question:\n\nContext:\n' || context || '\n\nQuestion: ' || question);
