# ollama.sql

Ollama and LLM integration. Base URL via `OLLAMA_BASE_URL`.

| Macro | Description |
|-------|-------------|
| `ollama_base()` | Ollama base URL |
| `ollama_chat_with_tools(model_name, messages_json, tools_json)` | Chat (use `json_array()` for no tools) |
| `extract_tool_calls(response_body)` | Extract tool_calls from response |
| `extract_response(response_body)` | Extract text from response |
| `ollama_embed(model_name, text_input)` | Embedding vector (FLOAT[]) |
| `agent_call(model_name, system_prompt, user_prompt, tools_json)` | Structured agent call |
| `has_tool_calls(response_body)` | TRUE if response contains tool calls |
| `cosine_sim(vec1, vec2)` | Cosine similarity of two vectors |
| `embed(text_input)` | Embed with `nomic-embed-text` |
| `semantic_score(query_text, doc_text)` | Similarity of two embedded texts |
| `rag_query(question, context)` | Answer question from context (DeepSeek) |
| `rag_think(question, context)` | Deep reasoning (Kimi-Think) |

**Model shortcuts** (single `prompt` argument): `deepseek`, `kimi`, `kimi_think`, `gemini`, `gemini_flash`, `qwen3_coder`, `qwen3_vl`, `qwen`, `glm`, `minimax`, `gpt_oss`, `gpt_oss_small`, `gpt_codex`, `devstral`.
