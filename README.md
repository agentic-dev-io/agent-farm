<div align="center">
  <img src="https://raw.githubusercontent.com/bjoernbethge/agent-farm/master/assets/farm.jpg" alt="Agent Farm" width="100%" />
</div>

# Agent Farm

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1.0+-yellow.svg)](https://duckdb.org)
[![Ollama](https://img.shields.io/badge/Ollama-Run%%20Locally-white.svg)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io)
[![Query Farm](https://img.shields.io/badge/Powered%%20By-Query%%20Farm-orange.svg)](https://query.farm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DuckDB-powered MCP Server with SQL macros for LLM agents - Web Search, Python execution, RAG, and more.**

[DuckDB](https://duckdb.org) - [Ollama](https://ollama.com) - [Docker](https://www.docker.com) - [Query Farm](https://query.farm)

## Features

- **MCP Server**: Exposes DuckDB as an MCP server for Claude and other LLM clients
- **Auto-Discovery**: Automatically discovers MCP configurations from standard locations
- **LLM Integration**: SQL macros for calling Ollama models (local and cloud)
- **Tool Calling**: Full function calling support for agentic workflows
- **Web Search**: DuckDuckGo and Brave Search integration
- **Shell Execution**: Run shell commands and Python code via UV
- **Web Scraping**: Fetch and extract text from web pages
- **RAG Support**: Embeddings and vector similarity search
- **Rich Extensions**: Pre-configured with useful DuckDB community extensions

## Installation

Using uv (recommended):
    uv sync --dev

Or with pip:
    pip install -e .

## Quick Start

Run the MCP server:
    agent-farm

Or as a module:
    python -m agent_farm

## SQL Macros

### Cloud LLM Models (via Ollama)

SELECT deepseek('Explain quantum computing');
SELECT kimi_think('Solve this step by step: ...');
SELECT qwen3_coder('Write a Python function for...');

### Web Search

SELECT ddg_instant('Python programming');
SELECT ddg_abstract('machine learning');
SELECT brave_search('DuckDB tutorial');

### Shell and Python Execution

SELECT shell('ls -la');
SELECT py('print(2+2)');
SELECT py_with('requests', 'import requests; print(requests.__version__)');

### Web Scraping

SELECT fetch('https://example.com');
SELECT fetch_text('https://example.com');
SELECT fetch_json('https://api.example.com/data');

### File and Git Operations

SELECT read_file('path/to/file.txt');
SELECT git_status();
SELECT git_log(10);

### RAG and Embeddings

SELECT rag_query('What is the price?', 'Product: Widget, Price: 49.99');
SELECT embed('Hello world');
SELECT semantic_score('query', 'document');

### Combined Power Macros

SELECT search_and_summarize('What is DuckDB?');
SELECT analyze_page('https://example.com', 'What is this page about?');
SELECT review_code('src/main.py');

## Docker

docker build -t agent-farm .
docker run -it agent-farm

## Requirements

- Python >= 3.11
- DuckDB >= 1.1.0
- Ollama (for LLM features)

## License

MIT
