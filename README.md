<div align="center">
  <img src="assets/farm.png" alt="Agent Farm" width="100%" />
</div>

# Agent Farm

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1.0+-yellow.svg)](https://duckdb.org)
[![Ollama](https://img.shields.io/badge/Ollama-Run%20Locally-white.svg)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io)
[![Query Farm](https://img.shields.io/badge/Powered%20By-Query%20Farm-orange.svg)](https://query.farm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DuckDB-powered MCP Server with LLM integration via Ollama.**

[DuckDB](https://duckdb.org) • [Ollama](https://ollama.com) • [Docker](https://www.docker.com) • [Query Farm](https://query.farm)

## Features

- **MCP Server**: Exposes DuckDB as an MCP server for Claude and other LLM clients
- **Auto-Discovery**: Automatically discovers MCP configurations from standard locations
- **LLM Integration**: SQL macros for calling Ollama models (local & cloud)
- **Tool Calling**: Full function calling support for agentic workflows
- **Rich Extensions**: Pre-configured with useful DuckDB community extensions

## Installation

```bash
# Using uv (recommended)
uv sync --dev

# Or with pip
pip install -e .
```

## Quick Start

```bash
# Run the MCP server
agent-farm

# Or as a module
python -m agent_farm
```

## MCP Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-farm": {
      "command": "agent-farm"
    }
  }
}
```

## DuckDB Extensions

The following extensions are automatically loaded:

| Extension | Description |
|-----------|-------------|
| `httpfs` | HTTP filesystem access |
| `http_client` | HTTP POST/GET requests |
| `json` | JSON parsing |
| `icu` | Internationalization |
| `duckdb_mcp` | MCP server functionality |
| `jsonata` | JSONata query language |
| `duckpgq` | Graph algorithms (SQL/PGQ) |
| `bitfilters` | Probabilistic filters |
| `lindel` | Z-Order/Hilbert curves |
| `vss` | Vector similarity search |
| `htmlstringify` | HTML to text |
| `lsh` | Locality sensitive hashing |
| `shellfs` | Shell commands as tables |
| `zipfs` | Read ZIP archives |
| `radio` | WebSocket & Redis PubSub |

## SQL Macros

### Cloud LLM Models (via Ollama)

```sql
-- Simple chat
SELECT deepseek('Explain quantum computing');
SELECT kimi('Write a haiku about databases');
SELECT gemini('What is DuckDB?');

-- With thinking/reasoning
SELECT kimi_think('Solve this step by step: ...');

-- Code generation
SELECT qwen3_coder('Write a Python function for...');
```

### Available Models

| Macro | Model | Size |
|-------|-------|------|
| `deepseek(prompt)` | DeepSeek V3.1 | 671B |
| `kimi(prompt)` | Kimi K2 | 1T |
| `kimi_think(prompt)` | Kimi K2 Thinking | 1T |
| `gemini(prompt)` | Gemini 3 Pro | - |
| `qwen3_coder(prompt)` | Qwen3 Coder | 480B |
| `qwen3_vl(prompt)` | Qwen3 VL (Vision) | 235B |
| `glm(prompt)` | GLM 4.6 | - |
| `minimax(prompt)` | MiniMax M2 | - |
| `gpt_oss(prompt)` | GPT-OSS | 120B |

### Tool Calling / Function Calling

```sql
-- Define a tool
SELECT mcp_to_ollama_tool(
    'get_weather',
    'Get current weather for a city',
    '{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}'
) AS tool_def;

-- Call model with tools
SELECT deepseek_tools(
    'What is the weather in Berlin?',
    '[{"type":"function","function":{"name":"get_weather",...}}]'
);

-- Full agent call with system prompt
SELECT agent_call(
    'deepseek-v3.1:671b-cloud',
    'You are a helpful assistant with access to tools.',
    'What is the weather in Berlin?',
    tools_json
);

-- Check for tool calls in response
SELECT has_tool_calls(response);
SELECT extract_tool_calls(response);
```

### RAG Helpers

```sql
-- Standard RAG with DeepSeek
SELECT rag_query('What is the price?', 'Product: Widget, Price: $49.99');

-- RAG with deep reasoning (Kimi Thinking)
SELECT rag_think('Analyze the implications', context_text);
```

## MCP Auto-Discovery

The server automatically discovers MCP configurations from:

- `./mcp.json` (project local)
- `~/.config/claude/claude_desktop_config.json` (Linux)
- `~/AppData/Roaming/Claude/claude_desktop_config.json` (Windows)
- `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

Discovered servers are registered in the `mcp_servers` table:

```sql
SELECT * FROM mcp_servers;
```

## Docker

If extensions fail to load on Windows, use the Docker image:

```bash
docker build -t farmer-agent .
docker run -it farmer-agent
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
pytest

# Lint
ruff check .
```

## Requirements

- Python >= 3.11
- DuckDB >= 1.1.0
- Ollama (for LLM features)

## License

MIT
