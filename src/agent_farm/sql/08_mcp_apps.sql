-- 08_mcp_apps.sql - MCP Apps Extension (ext-apps) with minijinja templates

-- =============================================================================
-- MCP APPS TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS mcp_apps (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    app_type VARCHAR NOT NULL,
    description VARCHAR,
    org_id VARCHAR,
    template_id VARCHAR,
    schema_input JSON,
    schema_output JSON,
    csp VARCHAR DEFAULT 'default-src ''self''',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_app_templates (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    template TEXT NOT NULL,
    base_template VARCHAR,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_app_instances (
    instance_id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'active',
    input_data JSON,
    output_data JSON,
    rendered_html TEXT,
    created_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS onboarding_profiles (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    focus JSON,
    icon VARCHAR,
    defaults JSON,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id VARCHAR PRIMARY KEY DEFAULT 'default',
    profile_id VARCHAR,
    custom_settings JSON,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- =============================================================================
-- BASE TEMPLATES (minijinja)
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, template) VALUES
('base', 'Base Template', '<!DOCTYPE html>
<html lang="de" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title | default(value="App") }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card-hover { transition: all 0.2s ease; }
        .card-hover:hover { transform: translateY(-2px); box-shadow: 0 10px 25px -5px rgb(0 0 0 / 0.1); }
    </style>
</head>
<body class="h-full bg-gray-50 text-gray-900">
    <div id="app" class="min-h-full p-6">
        {{ content }}
    </div>
    <script>
        const MCP = {
            instanceId: "{{ instance_id }}",
            submit(result) {
                window.parent.postMessage({ type: "app_result", instanceId: this.instanceId, result }, "*");
            },
            close() {
                window.parent.postMessage({ type: "app_close", instanceId: this.instanceId }, "*");
            }
        };
        {{ script | default(value="") }}
    </script>
</body>
</html>') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- DESIGN CHOICE TEMPLATE
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('design-choices', 'Design Choices', 'base', '
<div class="max-w-4xl mx-auto">
    <div class="mb-8">
        <h1 class="text-2xl font-bold">{{ title }}</h1>
        {% if description %}<p class="mt-2 text-gray-600">{{ description }}</p>{% endif %}
    </div>

    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3" id="options">
        {% for opt in options %}
        <div class="card-hover bg-white rounded-xl p-6 border-2 border-transparent cursor-pointer hover:border-indigo-400"
             data-id="{{ opt.id }}" onclick="selectOption(''{{ opt.id }}'')">
            {% if opt.icon %}<div class="text-3xl mb-3">{{ opt.icon }}</div>{% endif %}
            <h3 class="font-semibold text-lg">{{ opt.title }}</h3>
            {% if opt.description %}<p class="mt-2 text-sm text-gray-600">{{ opt.description }}</p>{% endif %}
            {% if opt.tags %}
            <div class="mt-4 flex flex-wrap gap-2">
                {% for tag in opt.tags %}<span class="px-2 py-1 text-xs rounded-full bg-indigo-100 text-indigo-700">{{ tag }}</span>{% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <div class="mt-8 hidden" id="rationale-box">
        <label class="block text-sm font-medium mb-2">Begründung (optional)</label>
        <textarea id="rationale" rows="3" class="w-full rounded-lg border-gray-300 p-3" placeholder="Warum diese Wahl?"></textarea>
    </div>

    <div class="mt-8 flex justify-end gap-4">
        <button onclick="MCP.close()" class="px-4 py-2 text-gray-600 hover:text-gray-900">Abbrechen</button>
        <button id="submit-btn" disabled onclick="submitChoice()"
                class="px-6 py-2 bg-indigo-500 text-white rounded-lg font-medium disabled:opacity-50 hover:bg-indigo-600">
            Auswählen
        </button>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

-- Script for design-choices (stored separately for clarity)
INSERT INTO mcp_app_templates (id, name, template) VALUES
('design-choices-script', 'Design Choices Script', '
let selectedId = null;
function selectOption(id) {
    document.querySelectorAll("[data-id]").forEach(el => {
        el.classList.remove("border-indigo-500", "ring-2", "ring-indigo-500");
        el.classList.add("border-transparent");
    });
    const card = document.querySelector(`[data-id="${id}"]`);
    card.classList.remove("border-transparent");
    card.classList.add("border-indigo-500", "ring-2", "ring-indigo-500");
    selectedId = id;
    document.getElementById("rationale-box").classList.remove("hidden");
    document.getElementById("submit-btn").disabled = false;
}
function submitChoice() {
    if (!selectedId) return;
    MCP.submit({ selected_id: selectedId, rationale: document.getElementById("rationale").value || null });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- ONBOARDING PROFILE TEMPLATE
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('profile-choices', 'Profile Choices', 'base', '
<div class="max-w-3xl mx-auto">
    <div class="mb-8 text-center">
        <h1 class="text-3xl font-bold">Willkommen!</h1>
        <p class="mt-2 text-gray-600">Wähle dein Profil, um loszulegen</p>
    </div>

    <div class="grid gap-6 md:grid-cols-2" id="profiles">
        {% for p in profiles %}
        <div class="card-hover bg-white rounded-2xl p-8 border-2 border-transparent cursor-pointer hover:border-indigo-400 text-center"
             data-id="{{ p.id }}" onclick="selectProfile(''{{ p.id }}'')">
            {% if p.icon %}<div class="text-5xl mb-4">{{ p.icon }}</div>{% endif %}
            <h3 class="font-bold text-xl">{{ p.name }}</h3>
            {% if p.description %}<p class="mt-2 text-gray-600">{{ p.description }}</p>{% endif %}
            {% if p.focus %}
            <div class="mt-4 flex flex-wrap justify-center gap-2">
                {% for f in p.focus %}<span class="px-3 py-1 text-sm rounded-full bg-gray-100">{{ f }}</span>{% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <div class="mt-8 flex justify-center">
        <button id="submit-btn" disabled onclick="submitProfile()"
                class="px-8 py-3 bg-indigo-500 text-white rounded-xl font-medium disabled:opacity-50 hover:bg-indigo-600">
            Profil auswählen
        </button>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('profile-choices-script', 'Profile Choices Script', '
let selectedProfile = null;
function selectProfile(id) {
    document.querySelectorAll("[data-id]").forEach(el => {
        el.classList.remove("border-indigo-500", "ring-2", "ring-indigo-500");
        el.classList.add("border-transparent");
    });
    const card = document.querySelector(`[data-id="${id}"]`);
    card.classList.remove("border-transparent");
    card.classList.add("border-indigo-500", "ring-2", "ring-indigo-500");
    selectedProfile = id;
    document.getElementById("submit-btn").disabled = false;
}
function submitProfile() {
    if (!selectedProfile) return;
    MCP.submit({ profile_id: selectedProfile });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- DOCUMENT VIEWER TEMPLATE
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('document-viewer', 'Document Viewer', 'base', '
<div class="max-w-4xl mx-auto">
    <div class="mb-4 flex justify-between items-center">
        <h1 class="text-xl font-bold">{{ title | default(value="Dokument") }}</h1>
        <button onclick="MCP.close()" class="text-gray-500 hover:text-gray-700">Schließen</button>
    </div>
    <div class="bg-white rounded-xl p-6 prose max-w-none" id="content">
        {{ content }}
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- CHART VIEWER TEMPLATE
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('chart-viewer', 'Chart Viewer', 'base', '
<div class="max-w-4xl mx-auto">
    <div class="mb-4 flex justify-between items-center">
        <h1 class="text-xl font-bold">{{ title | default(value="Chart") }}</h1>
        <button onclick="MCP.close()" class="text-gray-500 hover:text-gray-700">Schließen</button>
    </div>
    <div class="bg-white rounded-xl p-6">
        <canvas id="chart" width="800" height="400"></canvas>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('chart-viewer-script', 'Chart Viewer Script', '
const ctx = document.getElementById("chart").getContext("2d");
const chartData = {{ data | json_encode }};
const chartType = "{{ chart_type }}";
// Simple bar chart rendering (extend with Chart.js if needed)
if (chartData && chartData.labels && chartData.values) {
    const max = Math.max(...chartData.values);
    const barWidth = 60;
    const gap = 20;
    ctx.fillStyle = "#6366f1";
    chartData.values.forEach((v, i) => {
        const h = (v / max) * 350;
        ctx.fillRect(i * (barWidth + gap) + 50, 400 - h, barWidth, h);
        ctx.fillStyle = "#374151";
        ctx.font = "12px sans-serif";
        ctx.fillText(chartData.labels[i], i * (barWidth + gap) + 50, 420);
        ctx.fillStyle = "#6366f1";
    });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- SEED DEFAULT APPS
-- =============================================================================

INSERT INTO mcp_apps (id, name, app_type, description, org_id, template_id) VALUES
('app.studio.design-choices', 'Design Choices', 'choice', 'Präsentiere Design-Optionen zur Auswahl', 'studio-org', 'design-choices'),
('app.onboarding.profile-choices', 'Profile Selection', 'choice', 'Onboarding Profil-Auswahl', NULL, 'profile-choices'),
('app.studio.document', 'Document Viewer', 'viewer', 'Dokument-Anzeige', 'studio-org', 'document-viewer'),
('app.studio.chart', 'Chart Viewer', 'viewer', 'Diagramm-Anzeige', 'studio-org', 'chart-viewer'),
('app.settings', 'Settings', 'config', 'Benutzer-Einstellungen', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- SEED ONBOARDING PROFILES
-- =============================================================================

INSERT INTO onboarding_profiles (id, name, description, icon, focus, defaults) VALUES
('developer', 'Entwickler', 'Code, Pipelines, Git-Integration', '💻', '["code", "git", "testing"]'::JSON, '{"theme": "dark", "editor": "vim"}'::JSON),
('designer', 'Designer', 'Kreativ, Briefings, Asset-Management', '🎨', '["design", "assets", "specs"]'::JSON, '{"theme": "light", "preview": true}'::JSON),
('manager', 'Projektleitung', 'Übersicht, Planung, Dokumentation', '📊', '["planning", "docs", "reports"]'::JSON, '{"theme": "light", "dashboard": true}'::JSON),
('researcher', 'Researcher', 'Recherche, Analyse, Zusammenfassungen', '🔍', '["search", "analysis", "notes"]'::JSON, '{"theme": "auto", "sources": true}'::JSON)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- MINIJINJA RENDER MACROS
-- =============================================================================

-- Render a template with context
CREATE OR REPLACE MACRO render_template(template_id_param, context_json) AS (
    SELECT minijinja_render(
        (SELECT template FROM mcp_app_templates WHERE id = template_id_param),
        context_json
    )
);

-- Render app with base template composition
CREATE OR REPLACE MACRO render_app(app_id_param, instance_id_param, input_json) AS (
    WITH app AS (
        SELECT * FROM mcp_apps WHERE id = app_id_param
    ),
    tpl AS (
        SELECT * FROM mcp_app_templates WHERE id = (SELECT template_id FROM app)
    ),
    base AS (
        SELECT template FROM mcp_app_templates WHERE id = COALESCE((SELECT base_template FROM tpl), 'base')
    ),
    script AS (
        SELECT template FROM mcp_app_templates WHERE id = (SELECT template_id FROM app) || '-script'
    ),
    content_rendered AS (
        SELECT minijinja_render((SELECT template FROM tpl), input_json) as html
    )
    SELECT minijinja_render(
        (SELECT template FROM base),
        json_object(
            'title', (SELECT name FROM app),
            'instance_id', instance_id_param,
            'content', (SELECT html FROM content_rendered),
            'script', (SELECT template FROM script)
        )
    )
);

-- =============================================================================
-- APP INSTANCE MANAGEMENT WITH RENDERING
-- =============================================================================

-- Open an app and render HTML
CREATE OR REPLACE MACRO open_app(app_id_param, session_id_param, input_json) AS (
    WITH new_instance AS (
        INSERT INTO mcp_app_instances (instance_id, app_id, session_id, status, input_data)
        VALUES (
            'inst-' || substr(md5(random()::VARCHAR), 1, 8),
            app_id_param,
            session_id_param,
            'active',
            input_json::JSON
        )
        RETURNING *
    ),
    rendered AS (
        SELECT render_app(app_id_param, (SELECT instance_id FROM new_instance), input_json) as html
    )
    UPDATE mcp_app_instances
    SET rendered_html = (SELECT html FROM rendered)
    WHERE instance_id = (SELECT instance_id FROM new_instance)
    RETURNING json_object(
        'instance_id', instance_id,
        'app_id', app_id,
        'status', 'opened',
        'html', rendered_html
    )
);

-- Close app with result
CREATE OR REPLACE MACRO close_app(instance_id_param, output_json) AS (
    UPDATE mcp_app_instances
    SET status = 'closed', output_data = output_json::JSON, completed_at = now()
    WHERE instance_id = instance_id_param
    RETURNING json_object(
        'instance_id', instance_id,
        'status', 'closed',
        'output', output_data
    )
);

-- Get rendered HTML for instance
CREATE OR REPLACE MACRO get_app_html(instance_id_param) AS (
    SELECT rendered_html FROM mcp_app_instances WHERE instance_id = instance_id_param
);

-- =============================================================================
-- STUDIO ORG APP TOOLS
-- =============================================================================

CREATE OR REPLACE MACRO studio_present_choices(session_id_param, title, description, options_json) AS (
    SELECT open_app(
        'app.studio.design-choices',
        session_id_param,
        json_object('title', title, 'description', description, 'options', json(options_json))
    )
);

CREATE OR REPLACE MACRO studio_commit_choice(instance_id_param, selected_id, rationale) AS (
    WITH closed AS (
        SELECT close_app(instance_id_param, json_object('selected_id', selected_id, 'rationale', rationale)) as result
    ),
    logged AS (
        INSERT INTO audit_log (session_id, entry_type, tool_name, parameters, result, decision)
        SELECT
            (SELECT session_id FROM mcp_app_instances WHERE instance_id = instance_id_param),
            'app_choice', 'studio_commit_choice',
            json_object('instance_id', instance_id_param, 'selected_id', selected_id),
            closed.result, 'committed'
        FROM closed
        RETURNING id
    )
    SELECT json_object('status', 'committed', 'selected_id', selected_id, 'rationale', rationale, 'audit_id', (SELECT id FROM logged))
);

CREATE OR REPLACE MACRO studio_view_document(session_id_param, content, format) AS (
    SELECT open_app('app.studio.document', session_id_param, json_object('content', content, 'format', COALESCE(format, 'markdown')))
);

CREATE OR REPLACE MACRO studio_view_chart(session_id_param, chart_type, data_json, title) AS (
    SELECT open_app('app.studio.chart', session_id_param, json_object('chart_type', chart_type, 'data', json(data_json), 'title', title))
);

-- =============================================================================
-- ONBOARDING TOOLS
-- =============================================================================

CREATE OR REPLACE MACRO list_profiles() AS (
    SELECT json_group_array(json_object('id', id, 'name', name, 'description', description, 'focus', focus, 'icon', icon))
    FROM onboarding_profiles
);

CREATE OR REPLACE MACRO onboarding_select_profile(session_id_param) AS (
    SELECT open_app('app.onboarding.profile-choices', session_id_param, json_object('profiles', (SELECT list_profiles())))
);

CREATE OR REPLACE MACRO onboarding_commit_profile(user_id_param, profile_id_param) AS (
    WITH profile AS (SELECT * FROM onboarding_profiles WHERE id = profile_id_param),
    upsert AS (
        INSERT INTO user_profile (user_id, profile_id, updated_at)
        VALUES (user_id_param, profile_id_param, now())
        ON CONFLICT (user_id) DO UPDATE SET profile_id = profile_id_param, updated_at = now()
        RETURNING *
    )
    SELECT json_object(
        'status', 'profile_set',
        'user_id', user_id_param,
        'profile', (SELECT json_object('id', id, 'name', name, 'defaults', defaults) FROM profile)
    )
);

CREATE OR REPLACE MACRO get_user_profile(user_id_param) AS (
    SELECT json_object(
        'profile_id', up.profile_id,
        'profile', json_object('id', p.id, 'name', p.name, 'description', p.description, 'focus', p.focus, 'defaults', p.defaults),
        'custom_settings', up.custom_settings
    )
    FROM user_profile up
    LEFT JOIN onboarding_profiles p ON up.profile_id = p.id
    WHERE up.user_id = user_id_param
);

-- =============================================================================
-- SETTINGS TOOLS
-- =============================================================================

CREATE OR REPLACE MACRO open_settings(session_id_param, user_id_param) AS (
    SELECT open_app('app.settings', session_id_param, json_object(
        'current_profile', get_user_profile(user_id_param),
        'available_profiles', list_profiles(),
        'orgs', (SELECT json_group_array(json_object('id', id, 'name', name)) FROM orgs)
    ))
);

CREATE OR REPLACE MACRO save_settings(user_id_param, settings_json) AS (
    UPDATE user_profile SET custom_settings = settings_json::JSON, updated_at = now()
    WHERE user_id = user_id_param
    RETURNING json_object('status', 'saved', 'user_id', user_id)
);

-- =============================================================================
-- TOOL SCHEMA FOR AGENTS
-- =============================================================================

CREATE OR REPLACE MACRO studio_org_apps_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'present_design_choices',
            'description', 'Präsentiere Design-Optionen zur Auswahl (öffnet UI)',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'title', json_object('type', 'string'),
                'description', json_object('type', 'string'),
                'options', json_object('type', 'array', 'items', json_object('type', 'object'))
            ), 'required', json_array('title', 'options'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'view_document',
            'description', 'Zeige Dokument im Viewer',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'content', json_object('type', 'string'),
                'format', json_object('type', 'string', 'enum', json_array('markdown', 'html', 'text'))
            ), 'required', json_array('content'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'view_chart',
            'description', 'Zeige Chart/Diagramm',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'chart_type', json_object('type', 'string', 'enum', json_array('bar', 'line', 'pie')),
                'data', json_object('type', 'object'),
                'title', json_object('type', 'string')
            ), 'required', json_array('chart_type', 'data'))
        ))
    )
);

CREATE OR REPLACE MACRO execute_studio_app_tool(session_id_param, tool_name, tool_params) AS (
    SELECT CASE tool_name
        WHEN 'present_design_choices' THEN studio_present_choices(
            session_id_param,
            json_extract_string(tool_params, '$.title'),
            json_extract_string(tool_params, '$.description'),
            json_extract_string(tool_params, '$.options')
        )
        WHEN 'view_document' THEN studio_view_document(
            session_id_param,
            json_extract_string(tool_params, '$.content'),
            json_extract_string(tool_params, '$.format')
        )
        WHEN 'view_chart' THEN studio_view_chart(
            session_id_param,
            json_extract_string(tool_params, '$.chart_type'),
            json_extract_string(tool_params, '$.data'),
            json_extract_string(tool_params, '$.title')
        )
        ELSE json_object('error', 'Unknown tool', 'tool', tool_name)
    END
);
