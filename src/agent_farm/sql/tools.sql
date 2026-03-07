-- tools.sql - Web search, shell, file ops, git macros

-- =============================================================================
-- WEB SEARCH
-- =============================================================================

-- DuckDuckGo Instant Answer API
CREATE OR REPLACE MACRO ddg_instant(query) AS (
    http_get(
        'https://api.duckduckgo.com/?q=' || url_encode(query) || '&format=json&no_html=1'
    ).body::JSON
);

-- DuckDuckGo abstract text for a query
CREATE OR REPLACE MACRO ddg_abstract(query) AS (
    json_extract_string(ddg_instant(query), '$.Abstract')
);

-- DuckDuckGo related topics for a query
CREATE OR REPLACE MACRO ddg_related(query) AS (
    json_extract(ddg_instant(query), '$.RelatedTopics')
);

-- DuckDuckGo definition for a query term
CREATE OR REPLACE MACRO ddg_definition(query) AS (
    json_extract_string(ddg_instant(query), '$.Definition')
);

-- Brave Search web results (requires BRAVE_API_KEY)
CREATE OR REPLACE MACRO brave_search(query) AS (
    http_get(
        'https://api.search.brave.com/res/v1/web/search?q=' || url_encode(query),
        MAP {'X-Subscription-Token': get_secret('brave_api_key')},
        MAP {}
    ).body::JSON
);

-- Brave Search results array (web.results)
CREATE OR REPLACE MACRO brave_results(query) AS (
    json_extract(brave_search(query), '$.web.results')
);

-- Brave News search results (requires BRAVE_API_KEY)
CREATE OR REPLACE MACRO brave_news(query) AS (
    http_get(
        'https://api.search.brave.com/res/v1/news/search?q=' || url_encode(query),
        MAP {'X-Subscription-Token': get_secret('brave_api_key')},
        MAP {}
    ).body::JSON
);

-- =============================================================================
-- SHELL / COMMAND EXECUTION (via shellfs)
-- =============================================================================

-- Run a shell command and return stdout (Linux/macOS via shellfs)
CREATE OR REPLACE MACRO shell(cmd) AS (
    (SELECT content FROM read_text(cmd || ' |'))
);

-- Run command and return CSV output as table
CREATE OR REPLACE MACRO shell_csv(cmd) AS TABLE
    SELECT * FROM read_csv(cmd || ' |', auto_detect=true);

-- Run command and return JSON output as table
CREATE OR REPLACE MACRO shell_json(cmd) AS TABLE
    SELECT * FROM read_json(cmd || ' |', auto_detect=true);

-- Run a Windows cmd.exe command and return output
CREATE OR REPLACE MACRO cmd(command) AS (
    (SELECT content FROM read_text('cmd /c ' || command || ' |'))
);

-- Run a PowerShell command and return output
CREATE OR REPLACE MACRO pwsh(command) AS (
    (SELECT content FROM read_text('pwsh -NoProfile -Command "' || replace(command, '"', '`"') || '" |'))
);

-- =============================================================================
-- PYTHON / UV EXECUTION
-- =============================================================================

-- Execute Python code inline via uv run python -c
CREATE OR REPLACE MACRO py(code) AS (
    (SELECT content FROM read_text('uv run python -c "' || replace(code, '"', chr(92) || '"') || '" |'))
);

-- Execute Python code with extra pip packages via uv run --with
CREATE OR REPLACE MACRO py_with(deps, code) AS (
    (SELECT content FROM read_text('uv run --with ' || deps || ' python -c "' || replace(code, '"', chr(92) || '"') || '" |'))
);

-- Execute a Python script file via uv run python
CREATE OR REPLACE MACRO py_script(script_path) AS (
    (SELECT content FROM read_text('uv run python ' || script_path || ' |'))
);

-- Execute a Python script with command-line arguments
CREATE OR REPLACE MACRO py_script_args(script_path, args) AS (
    (SELECT content FROM read_text('uv run python ' || script_path || ' ' || args || ' |'))
);

-- Evaluate a Python expression and return its printed result
CREATE OR REPLACE MACRO py_eval(expr) AS (
    (SELECT content FROM read_text('uv run python -c "print(' || replace(expr, '"', chr(92) || '"') || ')" |'))
);

-- =============================================================================
-- WEB SCRAPING / FETCH
-- =============================================================================

-- HTTP GET a URL and return raw response body
CREATE OR REPLACE MACRO web_fetch(url) AS (
    http_get(url).body
);

-- HTTP GET a URL and return response body as text
CREATE OR REPLACE MACRO fetch_text(url) AS (
    http_get(url).body
);

-- HTTP GET a URL and parse response body as JSON
CREATE OR REPLACE MACRO fetch_json(url) AS (
    http_get(url).body::JSON
);

-- HTTP GET with custom request headers map
CREATE OR REPLACE MACRO fetch_headers(url, headers_map) AS (
    http_get(url, headers_map, MAP {}).body
);

-- HTTP GET with browser User-Agent header to bypass bot blocks
CREATE OR REPLACE MACRO fetch_ua(url) AS (
    http_get(url, MAP {'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'}, MAP {}).body
);

-- HTTP POST with JSON body, returns parsed JSON response
CREATE OR REPLACE MACRO post_json(url, body_json) AS (
    http_post(
        url,
        headers := MAP {'Content-Type': 'application/json'},
        body := body_json
    ).body::JSON
);

-- HTTP POST with form-encoded body
CREATE OR REPLACE MACRO post_form(url, form_data) AS (
    http_post(
        url,
        headers := MAP {'Content-Type': 'application/x-www-form-urlencoded'},
        body := form_data
    ).body
);

-- =============================================================================
-- FILE OPERATIONS
-- =============================================================================

-- Read a local file and return its text contents
CREATE OR REPLACE MACRO read_file(path) AS (
    (SELECT content FROM read_text(path))
);

-- List directory contents with ls -la (Linux/macOS)
CREATE OR REPLACE MACRO ls(path) AS (
    (SELECT content FROM read_text('ls -la ' || path || ' |'))
);

-- List directory contents with Windows dir command
CREATE OR REPLACE MACRO dir_list(path) AS (
    (SELECT content FROM read_text('dir "' || path || '" |'))
);

-- Find files matching a name pattern in a directory (Linux/macOS find)
CREATE OR REPLACE MACRO find_files(path, pattern) AS (
    (SELECT content FROM read_text('find ' || path || ' -name "' || pattern || '" |'))
);

-- Find files matching a pattern using Windows dir /s /b
CREATE OR REPLACE MACRO find_win(path, pattern) AS (
    (SELECT content FROM read_text('dir /s /b "' || path || chr(92) || pattern || '" |'))
);

-- Read multiple files matching a glob pattern as a table
CREATE OR REPLACE MACRO cat_files(pattern) AS TABLE
    SELECT * FROM read_text(pattern);

-- =============================================================================
-- GIT OPERATIONS
-- =============================================================================

-- Show git working-tree status
CREATE OR REPLACE MACRO git_status() AS (
    (SELECT content FROM read_text('git status |'))
);

-- Show last n git log entries (one-line format)
CREATE OR REPLACE MACRO git_log(n) AS (
    (SELECT content FROM read_text('git log -' || n::VARCHAR || ' --oneline |'))
);

-- Show current git diff (unstaged changes)
CREATE OR REPLACE MACRO git_diff() AS (
    (SELECT content FROM read_text('git diff |'))
);

-- List all git branches (local and remote)
CREATE OR REPLACE MACRO git_branch() AS (
    (SELECT content FROM read_text('git branch -a |'))
);

-- =============================================================================
-- SYSTEM INFO
-- =============================================================================

-- Return OS, architecture, and Python version as JSON
CREATE OR REPLACE MACRO sys_info() AS (
    (SELECT content FROM read_text('uv run python -c "import platform,json;print(json.dumps(dict(system=platform.system(),release=platform.release(),machine=platform.machine(),python=platform.python_version())))" |'))
);

-- Read an environment variable by name (Linux/macOS)
CREATE OR REPLACE MACRO env_var(name) AS (
    (SELECT content FROM read_text('printenv ' || name || ' |'))
);

-- Return current working directory path (Linux/macOS)
CREATE OR REPLACE MACRO cwd() AS (
    (SELECT content FROM read_text('pwd |'))
);

-- Read an environment variable by name (Windows)
CREATE OR REPLACE MACRO env_var_win(name) AS (
    (SELECT content FROM read_text('cmd /c echo %' || name || '% |'))
);

-- Return current working directory path (Windows)
CREATE OR REPLACE MACRO cwd_win() AS (
    (SELECT content FROM read_text('cmd /c cd |'))
);

-- =============================================================================
-- DATA LOADING
-- =============================================================================

-- Load CSV from a URL into a table with auto-detected schema
CREATE OR REPLACE MACRO load_csv_url(url) AS TABLE
    SELECT * FROM read_csv(url, auto_detect=true);

-- Load JSON from a URL into a table with auto-detected schema
CREATE OR REPLACE MACRO load_json_url(url) AS TABLE
    SELECT * FROM read_json(url, auto_detect=true);

-- Load Parquet from a URL into a table
CREATE OR REPLACE MACRO load_parquet_url(url) AS TABLE
    SELECT * FROM read_parquet(url);

-- =============================================================================
-- POWER MACROS (LLM + Tools combined)
-- =============================================================================

-- Web search + LLM summarization in one call
CREATE OR REPLACE MACRO search_and_summarize(query) AS (
    deepseek(
        'Fasse die Suchergebnisse zusammen und beantworte: ' || query ||
        chr(10) || chr(10) || 'Suchergebnisse: ' || COALESCE(ddg_abstract(query), 'Keine Ergebnisse')
    )
);

-- Fetch a webpage and answer a question about it using LLM
CREATE OR REPLACE MACRO analyze_page(url, question) AS (
    deepseek(
        'Analysiere den Webseiten-Inhalt und beantworte: ' || question ||
        chr(10) || chr(10) || 'Inhalt: ' || fetch_text(url)
    )
);

-- LLM code review: bugs, improvements, security issues
CREATE OR REPLACE MACRO review_code(file_path) AS (
    deepseek(
        'Code Review - finde Bugs, Verbesserungen und Security Issues:' ||
        chr(10) || chr(10) || read_file(file_path)
    )
);

-- LLM step-by-step explanation of a source file
CREATE OR REPLACE MACRO explain_code(file_path) AS (
    deepseek('Erklaere diesen Code Schritt fuer Schritt:' || chr(10) || read_file(file_path))
);

-- LLM Python code generation for a task description
CREATE OR REPLACE MACRO generate_py(task) AS (
    deepseek('Schreibe Python-Code fuer: ' || task || ' - Gib NUR Code zurueck, kein Markdown.')
);

-- ElevenLabs text-to-speech (requires elevenlabs_key secret)
CREATE OR REPLACE MACRO elevenlabs_tts(text_input) AS TABLE
SELECT
    http_post(
        'https://api.elevenlabs.io/v1/tts/voice_id',
        headers := MAP {'xi-api-key': get_secret('elevenlabs_key')},
        body := json_object('text', text_input)
    ) AS audio_file_bytes;
