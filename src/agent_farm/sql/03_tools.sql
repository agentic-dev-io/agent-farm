-- 03_tools.sql - Web search, shell, file ops, git macros

-- =============================================================================
-- WEB SEARCH
-- =============================================================================

-- DuckDuckGo Instant Answer API
CREATE OR REPLACE MACRO ddg_instant(query) AS (
    http_get(
        'https://api.duckduckgo.com/?q=' || url_encode(query) || '&format=json&no_html=1'
    ).body::JSON
);

CREATE OR REPLACE MACRO ddg_abstract(query) AS (
    json_extract_string(ddg_instant(query), '$.Abstract')
);

CREATE OR REPLACE MACRO ddg_related(query) AS (
    json_extract(ddg_instant(query), '$.RelatedTopics')
);

CREATE OR REPLACE MACRO ddg_definition(query) AS (
    json_extract_string(ddg_instant(query), '$.Definition')
);

-- Brave Search API
CREATE OR REPLACE MACRO brave_search(query) AS (
    http_get(
        'https://api.search.brave.com/res/v1/web/search?q=' || url_encode(query),
        headers := MAP {'X-Subscription-Token': get_secret('brave_api_key')}
    ).body::JSON
);

CREATE OR REPLACE MACRO brave_results(query) AS (
    json_extract(brave_search(query), '$.web.results')
);

CREATE OR REPLACE MACRO brave_news(query) AS (
    http_get(
        'https://api.search.brave.com/res/v1/news/search?q=' || url_encode(query),
        headers := MAP {'X-Subscription-Token': get_secret('brave_api_key')}
    ).body::JSON
);

-- =============================================================================
-- SHELL / COMMAND EXECUTION (via shellfs)
-- =============================================================================

CREATE OR REPLACE MACRO shell(cmd) AS (
    (SELECT content FROM read_text(cmd || ' |'))
);

CREATE OR REPLACE MACRO shell_csv(cmd) AS TABLE
    SELECT * FROM read_csv(cmd || ' |', auto_detect=true);

CREATE OR REPLACE MACRO shell_json(cmd) AS TABLE
    SELECT * FROM read_json(cmd || ' |', auto_detect=true);

CREATE OR REPLACE MACRO cmd(command) AS (
    (SELECT content FROM read_text('cmd /c ' || command || ' |'))
);

CREATE OR REPLACE MACRO pwsh(command) AS (
    (SELECT content FROM read_text('pwsh -NoProfile -Command "' || replace(command, '"', '`"') || '" |'))
);

-- =============================================================================
-- PYTHON / UV EXECUTION
-- =============================================================================

CREATE OR REPLACE MACRO py(code) AS (
    (SELECT content FROM read_text('uv run python -c "' || replace(code, '"', chr(92) || '"') || '" |'))
);

CREATE OR REPLACE MACRO py_with(deps, code) AS (
    (SELECT content FROM read_text('uv run --with ' || deps || ' python -c "' || replace(code, '"', chr(92) || '"') || '" |'))
);

CREATE OR REPLACE MACRO py_script(script_path) AS (
    (SELECT content FROM read_text('uv run python ' || script_path || ' |'))
);

CREATE OR REPLACE MACRO py_script_args(script_path, args) AS (
    (SELECT content FROM read_text('uv run python ' || script_path || ' ' || args || ' |'))
);

CREATE OR REPLACE MACRO py_eval(expr) AS (
    (SELECT content FROM read_text('uv run python -c "print(' || replace(expr, '"', chr(92) || '"') || ')" |'))
);

-- =============================================================================
-- WEB SCRAPING / FETCH
-- =============================================================================

CREATE OR REPLACE MACRO web_fetch(url) AS (
    http_get(url).body
);

CREATE OR REPLACE MACRO fetch_text(url) AS (
    TRY(htmlstringify(http_get(url).body))
);

CREATE OR REPLACE MACRO fetch_json(url) AS (
    http_get(url).body::JSON
);

CREATE OR REPLACE MACRO fetch_headers(url, headers_map) AS (
    http_get(url, headers := headers_map).body
);

CREATE OR REPLACE MACRO fetch_ua(url) AS (
    http_get(url, headers := MAP {'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'}).body
);

CREATE OR REPLACE MACRO post_json(url, body_json) AS (
    http_post(
        url,
        headers := MAP {'Content-Type': 'application/json'},
        body := body_json
    ).body::JSON
);

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

CREATE OR REPLACE MACRO read_file(path) AS (
    (SELECT content FROM read_text(path))
);

CREATE OR REPLACE MACRO ls(path) AS (
    (SELECT content FROM read_text('ls -la ' || path || ' |'))
);

CREATE OR REPLACE MACRO dir_list(path) AS (
    (SELECT content FROM read_text('dir "' || path || '" |'))
);

CREATE OR REPLACE MACRO find_files(path, pattern) AS (
    (SELECT content FROM read_text('find ' || path || ' -name "' || pattern || '" |'))
);

CREATE OR REPLACE MACRO find_win(path, pattern) AS (
    (SELECT content FROM read_text('dir /s /b "' || path || chr(92) || pattern || '" |'))
);

CREATE OR REPLACE MACRO cat_files(pattern) AS TABLE
    SELECT * FROM read_text(pattern);

-- =============================================================================
-- GIT OPERATIONS
-- =============================================================================

CREATE OR REPLACE MACRO git_status() AS (
    (SELECT content FROM read_text('git status |'))
);

CREATE OR REPLACE MACRO git_log(n) AS (
    (SELECT content FROM read_text('git log -' || n::VARCHAR || ' --oneline |'))
);

CREATE OR REPLACE MACRO git_diff() AS (
    (SELECT content FROM read_text('git diff |'))
);

CREATE OR REPLACE MACRO git_branch() AS (
    (SELECT content FROM read_text('git branch -a |'))
);

-- =============================================================================
-- SYSTEM INFO
-- =============================================================================

CREATE OR REPLACE MACRO sys_info() AS (
    (SELECT content FROM read_text('uv run python -c "import platform,json;print(json.dumps(dict(system=platform.system(),release=platform.release(),machine=platform.machine(),python=platform.python_version())))" |'))
);

CREATE OR REPLACE MACRO env_var(name) AS (
    (SELECT content FROM read_text('printenv ' || name || ' |'))
);

CREATE OR REPLACE MACRO cwd() AS (
    (SELECT content FROM read_text('pwd |'))
);

CREATE OR REPLACE MACRO env_var_win(name) AS (
    (SELECT content FROM read_text('cmd /c echo %' || name || '% |'))
);

CREATE OR REPLACE MACRO cwd_win() AS (
    (SELECT content FROM read_text('cmd /c cd |'))
);

-- =============================================================================
-- DATA LOADING
-- =============================================================================

CREATE OR REPLACE MACRO load_csv_url(url) AS TABLE
    SELECT * FROM read_csv(url, auto_detect=true);

CREATE OR REPLACE MACRO load_json_url(url) AS TABLE
    SELECT * FROM read_json(url, auto_detect=true);

CREATE OR REPLACE MACRO load_parquet_url(url) AS TABLE
    SELECT * FROM read_parquet(url);

-- =============================================================================
-- POWER MACROS (LLM + Tools combined)
-- =============================================================================

CREATE OR REPLACE MACRO search_and_summarize(query) AS (
    deepseek(
        'Fasse die Suchergebnisse zusammen und beantworte: ' || query ||
        chr(10) || chr(10) || 'Suchergebnisse: ' || COALESCE(ddg_abstract(query), 'Keine Ergebnisse')
    )
);

CREATE OR REPLACE MACRO analyze_page(url, question) AS (
    deepseek(
        'Analysiere den Webseiten-Inhalt und beantworte: ' || question ||
        chr(10) || chr(10) || 'Inhalt: ' || fetch_text(url)
    )
);

CREATE OR REPLACE MACRO review_code(file_path) AS (
    deepseek(
        'Code Review - finde Bugs, Verbesserungen und Security Issues:' ||
        chr(10) || chr(10) || read_file(file_path)
    )
);

CREATE OR REPLACE MACRO explain_code(file_path) AS (
    deepseek('Erklaere diesen Code Schritt fuer Schritt:' || chr(10) || read_file(file_path))
);

CREATE OR REPLACE MACRO generate_py(task) AS (
    deepseek('Schreibe Python-Code fuer: ' || task || ' - Gib NUR Code zurueck, kein Markdown.')
);

-- External APIs
CREATE OR REPLACE MACRO elevenlabs_tts(text_input) AS TABLE
SELECT
    http_post(
        'https://api.elevenlabs.io/v1/tts/voice_id',
        headers := MAP {'xi-api-key': get_secret('elevenlabs_key')},
        body := json_object('text', text_input)
    ) AS audio_file_bytes;
