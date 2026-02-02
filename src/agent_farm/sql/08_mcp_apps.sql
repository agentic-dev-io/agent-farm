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
    <script>
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            colors: {
              surface: { 50: "#1a1a1a", 100: "#141414", 200: "#0d0d0d", 300: "#0a0a0a" },
              accent: { DEFAULT: "#22c55e", dim: "#16a34a", glow: "#4ade80" },
              muted: { DEFAULT: "#737373", light: "#a3a3a3" }
            },
            borderRadius: { pill: "9999px" },
            backdropBlur: { glass: "20px" }
          }
        }
      }
    </script>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Segoe UI", sans-serif; }
      .glass { background: rgba(26, 26, 26, 0.85); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.08); }
      .card-hover { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
      .card-hover:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(34, 197, 94, 0.15); border-color: rgba(34, 197, 94, 0.4); }
      .pill { padding: 6px 14px; border-radius: 9999px; font-size: 13px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); transition: all 0.15s; }
      .pill:hover { background: rgba(255,255,255,0.1); }
      .pill.active { background: rgba(34, 197, 94, 0.2); border-color: rgba(34, 197, 94, 0.5); color: #4ade80; }
      .glow-btn { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); box-shadow: 0 0 20px rgba(34, 197, 94, 0.3); }
      .glow-btn:hover { box-shadow: 0 0 30px rgba(34, 197, 94, 0.5); }
      .glow-btn:disabled { background: #333; box-shadow: none; opacity: 0.5; }
      ::selection { background: rgba(34, 197, 94, 0.3); }
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
    </style>
</head>
<body class="h-full bg-surface-300 text-white">
    <div id="app" class="min-h-full p-8">
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
<div class="max-w-5xl mx-auto">
    <!-- Header -->
    <div class="mb-10">
        <h1 class="text-2xl font-semibold tracking-tight">{{ title }}</h1>
        {% if description %}<p class="mt-2 text-muted-light text-sm">{{ description }}</p>{% endif %}
    </div>

    <!-- Mode Pills (like Seedance) -->
    {% if modes %}
    <div class="flex gap-2 mb-8">
        {% for mode in modes %}<button class="pill" data-mode="{{ mode.id }}">{{ mode.label }}</button>{% endfor %}
    </div>
    {% endif %}

    <!-- Options Grid -->
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3" id="options">
        {% for opt in options %}
        <div class="card-hover glass rounded-2xl p-5 cursor-pointer border border-white/5"
             data-id="{{ opt.id }}" onclick="selectOption(''{{ opt.id }}'')">
            {% if opt.preview %}
            <div class="aspect-video rounded-xl overflow-hidden mb-4 bg-surface-100">
                <img src="{{ opt.preview }}" class="w-full h-full object-cover" alt="{{ opt.title }}">
            </div>
            {% endif %}
            {% if opt.icon %}<div class="text-2xl mb-3">{{ opt.icon }}</div>{% endif %}
            <h3 class="font-medium text-white/90">{{ opt.title }}</h3>
            {% if opt.description %}<p class="mt-1.5 text-sm text-muted">{{ opt.description }}</p>{% endif %}
            {% if opt.tags %}
            <div class="mt-4 flex flex-wrap gap-1.5">
                {% for tag in opt.tags %}<span class="pill text-xs">{{ tag }}</span>{% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <!-- Input Bar (Seedance style) -->
    <div class="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4">
        <div class="glass rounded-2xl p-4">
            <div class="flex items-center gap-3">
                <div class="flex gap-2">
                    <button class="pill text-xs opacity-60">Template</button>
                </div>
                <input type="text" id="rationale"
                       class="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder-muted"
                       placeholder="Describe your choice or add context...">
                <div class="flex items-center gap-2">
                    <button onclick="MCP.close()" class="pill text-xs text-muted hover:text-white">Esc</button>
                    <button id="submit-btn" disabled onclick="submitChoice()"
                            class="glow-btn px-5 py-2 rounded-xl text-sm font-medium text-white disabled:cursor-not-allowed">
                        Select
                    </button>
                </div>
            </div>
        </div>
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
<div class="max-w-3xl mx-auto pt-12">
    <div class="mb-12 text-center">
        <h1 class="text-4xl font-bold bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">Willkommen</h1>
        <p class="mt-3 text-muted">Wähle dein Profil</p>
    </div>

    <div class="grid gap-4 md:grid-cols-2" id="profiles">
        {% for p in profiles %}
        <div class="card-hover glass rounded-2xl p-6 cursor-pointer text-center border border-white/5"
             data-id="{{ p.id }}" onclick="selectProfile(''{{ p.id }}'')">
            {% if p.icon %}<div class="text-4xl mb-4">{{ p.icon }}</div>{% endif %}
            <h3 class="font-semibold text-lg text-white/90">{{ p.name }}</h3>
            {% if p.description %}<p class="mt-2 text-sm text-muted">{{ p.description }}</p>{% endif %}
            {% if p.focus %}
            <div class="mt-4 flex flex-wrap justify-center gap-1.5">
                {% for f in p.focus %}<span class="pill text-xs">{{ f }}</span>{% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <div class="mt-10 flex justify-center">
        <button id="submit-btn" disabled onclick="submitProfile()"
                class="glow-btn px-8 py-3 rounded-xl font-medium text-white disabled:cursor-not-allowed">
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
    <div class="mb-6 flex justify-between items-center">
        <h1 class="text-xl font-semibold text-white/90">{{ title | default(value="Dokument") }}</h1>
        <button onclick="MCP.close()" class="pill text-xs">Schließen</button>
    </div>
    <div class="glass rounded-2xl p-6" id="content">
        <article class="prose prose-invert prose-sm max-w-none">{{ content }}</article>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- CHART VIEWER TEMPLATE
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('chart-viewer', 'Chart Viewer', 'base', '
<div class="max-w-4xl mx-auto">
    <div class="mb-6 flex justify-between items-center">
        <h1 class="text-xl font-semibold text-white/90">{{ title | default(value="Chart") }}</h1>
        <button onclick="MCP.close()" class="pill text-xs">Schließen</button>
    </div>
    <div class="glass rounded-2xl p-6">
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
    ctx.fillStyle = "#22c55e";
    chartData.values.forEach((v, i) => {
        const h = (v / max) * 350;
        ctx.fillRect(i * (barWidth + gap) + 50, 400 - h, barWidth, h);
        ctx.fillStyle = "#a3a3a3";
        ctx.font = "12px sans-serif";
        ctx.fillText(chartData.labels[i], i * (barWidth + gap) + 50, 420);
        ctx.fillStyle = "#22c55e";
    });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- VIBE CODING TEMPLATE - Smart code generation interface
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('vibe-coder', 'Vibe Coder', 'base', '
<div class="max-w-6xl mx-auto">
    <!-- Header with context pills -->
    <div class="flex items-center gap-4 mb-6">
        <div class="flex gap-2">
            {% for ctx in context %}<span class="pill active text-xs">{{ ctx }}</span>{% endfor %}
        </div>
        <div class="flex-1"></div>
        <span class="text-xs text-muted">{{ model | default(value="auto") }}</span>
    </div>

    <!-- Code Preview Area -->
    <div class="glass rounded-2xl overflow-hidden mb-6">
        <div class="flex items-center justify-between px-4 py-2 border-b border-white/5">
            <div class="flex gap-2">
                {% for f in files %}<button class="pill text-xs" data-file="{{ f.path }}">{{ f.name }}</button>{% endfor %}
            </div>
            <div class="flex gap-2">
                <button class="pill text-xs" onclick="copyCode()">Copy</button>
                <button class="pill text-xs" onclick="applyCode()">Apply</button>
            </div>
        </div>
        <pre class="p-4 text-sm overflow-auto max-h-96"><code id="code-preview" class="text-accent-glow">{{ code }}</code></pre>
    </div>

    <!-- Diff View (if changes) -->
    {% if diff %}
    <div class="glass rounded-2xl p-4 mb-6">
        <div class="text-xs text-muted mb-2">Changes</div>
        <pre class="text-sm"><code>{{ diff }}</code></pre>
    </div>
    {% endif %}

    <!-- Action Bar -->
    <div class="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4">
        <div class="glass rounded-2xl p-4">
            <div class="flex items-center gap-3">
                <div class="flex gap-2">
                    <button class="pill text-xs {{ mode_code }}" data-mode="code">Code</button>
                    <button class="pill text-xs {{ mode_refactor }}" data-mode="refactor">Refactor</button>
                    <button class="pill text-xs {{ mode_test }}" data-mode="test">Test</button>
                    <button class="pill text-xs {{ mode_docs }}" data-mode="docs">Docs</button>
                </div>
                <input type="text" id="prompt"
                       class="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder-muted"
                       placeholder="Describe what you want to build..." value="{{ prompt }}">
                <button id="submit-btn" onclick="submitVibe()"
                        class="glow-btn px-5 py-2 rounded-xl text-sm font-medium text-white">
                    Generate
                </button>
            </div>
        </div>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('vibe-coder-script', 'Vibe Coder Script', '
let currentMode = "code";
document.querySelectorAll("[data-mode]").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll("[data-mode]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentMode = btn.dataset.mode;
    });
});
function copyCode() {
    navigator.clipboard.writeText(document.getElementById("code-preview").textContent);
}
function applyCode() {
    MCP.submit({ action: "apply", code: document.getElementById("code-preview").textContent });
}
function submitVibe() {
    MCP.submit({ action: "generate", mode: currentMode, prompt: document.getElementById("prompt").value });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- SOLID DOCS TEMPLATE - Documentation generation/editing
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('solid-docs', 'Solid Docs', 'base', '
<div class="max-w-5xl mx-auto">
    <!-- Doc Type Selector -->
    <div class="flex gap-2 mb-8">
        <button class="pill {{ type_readme }}" data-type="readme">README</button>
        <button class="pill {{ type_api }}" data-type="api">API Docs</button>
        <button class="pill {{ type_guide }}" data-type="guide">Guide</button>
        <button class="pill {{ type_changelog }}" data-type="changelog">Changelog</button>
        <button class="pill {{ type_spec }}" data-type="spec">Spec</button>
    </div>

    <!-- Editor Area -->
    <div class="glass rounded-2xl overflow-hidden">
        <div class="flex border-b border-white/5">
            <button class="px-4 py-2 text-sm text-white/80 border-b-2 border-accent" data-view="edit">Edit</button>
            <button class="px-4 py-2 text-sm text-muted" data-view="preview">Preview</button>
            <button class="px-4 py-2 text-sm text-muted" data-view="diff">Diff</button>
        </div>
        <div class="p-4">
            <textarea id="doc-content" rows="20"
                class="w-full bg-transparent border-none outline-none text-sm text-white/90 font-mono resize-none"
                placeholder="# Documentation">{{ content }}</textarea>
        </div>
    </div>

    <!-- Metadata -->
    <div class="mt-6 glass rounded-2xl p-4">
        <div class="grid grid-cols-3 gap-4 text-sm">
            <div>
                <span class="text-muted">Target:</span>
                <span class="ml-2 text-white/80">{{ target | default(value="README.md") }}</span>
            </div>
            <div>
                <span class="text-muted">Format:</span>
                <span class="ml-2 text-white/80">{{ format | default(value="markdown") }}</span>
            </div>
            <div>
                <span class="text-muted">Status:</span>
                <span class="ml-2 pill text-xs active">{{ status | default(value="draft") }}</span>
            </div>
        </div>
    </div>

    <!-- Action Bar -->
    <div class="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4">
        <div class="glass rounded-2xl p-4">
            <div class="flex items-center gap-3">
                <button class="pill text-xs" onclick="MCP.close()">Cancel</button>
                <div class="flex-1"></div>
                <button class="pill text-xs" onclick="saveDraft()">Save Draft</button>
                <button class="glow-btn px-5 py-2 rounded-xl text-sm font-medium text-white" onclick="commitDoc()">
                    Commit
                </button>
            </div>
        </div>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('solid-docs-script', 'Solid Docs Script', '
function saveDraft() {
    MCP.submit({ action: "draft", content: document.getElementById("doc-content").value });
}
function commitDoc() {
    MCP.submit({ action: "commit", content: document.getElementById("doc-content").value });
}
document.querySelectorAll("[data-type]").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll("[data-type]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
    });
});') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- APPROVAL FLOW TEMPLATE - Human-in-the-loop decisions
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('approval-flow', 'Approval Flow', 'base', '
<div class="max-w-2xl mx-auto">
    <!-- Alert Header -->
    <div class="glass rounded-2xl p-6 mb-6 border-l-4 border-{{ severity | default(value="accent") }}">
        <div class="flex items-start gap-4">
            <div class="text-3xl">{{ icon | default(value="⚠️") }}</div>
            <div>
                <h2 class="text-lg font-semibold text-white">{{ title }}</h2>
                <p class="mt-1 text-sm text-muted">{{ description }}</p>
            </div>
        </div>
    </div>

    <!-- Details -->
    <div class="glass rounded-2xl p-4 mb-6">
        <div class="text-xs text-muted uppercase tracking-wider mb-3">Details</div>
        <div class="space-y-2 text-sm">
            {% for item in details %}
            <div class="flex justify-between">
                <span class="text-muted">{{ item.label }}</span>
                <span class="text-white/80 font-mono">{{ item.value }}</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Risk Assessment -->
    {% if risk %}
    <div class="glass rounded-2xl p-4 mb-6">
        <div class="text-xs text-muted uppercase tracking-wider mb-3">Risk Assessment</div>
        <div class="flex items-center gap-4">
            <div class="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                <div class="h-full bg-{{ risk_color | default(value="accent") }}" style="width: {{ risk }}%"></div>
            </div>
            <span class="text-sm text-muted">{{ risk }}%</span>
        </div>
    </div>
    {% endif %}

    <!-- Actions -->
    <div class="flex gap-4">
        <button onclick="deny()" class="flex-1 py-3 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition">
            Deny
        </button>
        <button onclick="approve()" class="flex-1 py-3 rounded-xl glow-btn text-white">
            Approve
        </button>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('approval-flow-script', 'Approval Flow Script', '
function approve() { MCP.submit({ decision: "approved" }); }
function deny() { MCP.submit({ decision: "denied" }); }') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- TERMINAL/SHELL TEMPLATE - Command execution interface
-- =============================================================================

INSERT INTO mcp_app_templates (id, name, base_template, template) VALUES
('terminal', 'Terminal', 'base', '
<div class="max-w-4xl mx-auto">
    <div class="glass rounded-2xl overflow-hidden">
        <!-- Tab Bar -->
        <div class="flex items-center px-4 py-2 border-b border-white/5 bg-surface-200">
            <div class="flex gap-1.5">
                <div class="w-3 h-3 rounded-full bg-red-500/80"></div>
                <div class="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                <div class="w-3 h-3 rounded-full bg-green-500/80"></div>
            </div>
            <div class="flex-1 text-center text-xs text-muted">{{ cwd | default(value="~") }}</div>
        </div>

        <!-- Output Area -->
        <div id="output" class="p-4 h-96 overflow-auto font-mono text-sm">
            {% for line in output %}
            <div class="{{ line.class | default(value=''text-white/80'') }}">{{ line.text }}</div>
            {% endfor %}
        </div>

        <!-- Input -->
        <div class="flex items-center px-4 py-3 border-t border-white/5 bg-surface-200">
            <span class="text-accent mr-2">$</span>
            <input type="text" id="cmd"
                   class="flex-1 bg-transparent border-none outline-none text-sm text-white font-mono"
                   placeholder="Enter command..." autofocus>
            <button onclick="runCmd()" class="pill text-xs">Run</button>
        </div>
    </div>
</div>') ON CONFLICT (id) DO NOTHING;

INSERT INTO mcp_app_templates (id, name, template) VALUES
('terminal-script', 'Terminal Script', '
document.getElementById("cmd").addEventListener("keydown", e => {
    if (e.key === "Enter") runCmd();
});
function runCmd() {
    const cmd = document.getElementById("cmd").value;
    if (!cmd) return;
    MCP.submit({ command: cmd });
}') ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- SEED DEFAULT APPS
-- =============================================================================

INSERT INTO mcp_apps (id, name, app_type, description, org_id, template_id) VALUES
('app.studio.design-choices', 'Design Choices', 'choice', 'Präsentiere Design-Optionen zur Auswahl', 'studio-org', 'design-choices'),
('app.onboarding.profile-choices', 'Profile Selection', 'choice', 'Onboarding Profil-Auswahl', NULL, 'profile-choices'),
('app.studio.document', 'Document Viewer', 'viewer', 'Dokument-Anzeige', 'studio-org', 'document-viewer'),
('app.studio.chart', 'Chart Viewer', 'viewer', 'Diagramm-Anzeige', 'studio-org', 'chart-viewer'),
('app.dev.vibe-coder', 'Vibe Coder', 'editor', 'Smart code generation', 'dev-org', 'vibe-coder'),
('app.studio.solid-docs', 'Solid Docs', 'editor', 'Documentation generator', 'studio-org', 'solid-docs'),
('app.ops.terminal', 'Terminal', 'shell', 'Command execution', 'ops-org', 'terminal'),
('app.approval', 'Approval Flow', 'approval', 'Human-in-the-loop decisions', NULL, 'approval-flow'),
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

-- =============================================================================
-- VIBE CODER TOOLS (DevOrg)
-- =============================================================================

CREATE OR REPLACE MACRO dev_open_vibe_coder(session_id_param, context_array, code, prompt) AS (
    SELECT open_app('app.dev.vibe-coder', session_id_param, json_object(
        'context', json(context_array),
        'code', code,
        'prompt', prompt,
        'files', json_array()
    ))
);

CREATE OR REPLACE MACRO dev_vibe_generate(session_id_param, mode, prompt, files_json) AS (
    SELECT open_app('app.dev.vibe-coder', session_id_param, json_object(
        'mode', mode,
        'prompt', prompt,
        'files', json(files_json),
        'context', json_array(mode)
    ))
);

-- =============================================================================
-- SOLID DOCS TOOLS (StudioOrg)
-- =============================================================================

CREATE OR REPLACE MACRO studio_open_docs(session_id_param, doc_type, content, target) AS (
    SELECT open_app('app.studio.solid-docs', session_id_param, json_object(
        'type', doc_type,
        'content', content,
        'target', target,
        'status', 'draft'
    ))
);

CREATE OR REPLACE MACRO studio_generate_readme(session_id_param, project_info) AS (
    SELECT open_app('app.studio.solid-docs', session_id_param, json_object(
        'type', 'readme',
        'content', '',
        'target', 'README.md',
        'project', json(project_info),
        'type_readme', 'active'
    ))
);

-- =============================================================================
-- TERMINAL TOOLS (OpsOrg)
-- =============================================================================

CREATE OR REPLACE MACRO ops_open_terminal(session_id_param, cwd, output_lines) AS (
    SELECT open_app('app.ops.terminal', session_id_param, json_object(
        'cwd', cwd,
        'output', json(output_lines)
    ))
);

-- =============================================================================
-- APPROVAL FLOW TOOLS (Cross-Org)
-- =============================================================================

CREATE OR REPLACE MACRO request_approval(session_id_param, title, description, details_json, risk_percent) AS (
    SELECT open_app('app.approval', session_id_param, json_object(
        'title', title,
        'description', description,
        'details', json(details_json),
        'risk', risk_percent,
        'icon', CASE
            WHEN risk_percent > 70 THEN '🚨'
            WHEN risk_percent > 40 THEN '⚠️'
            ELSE '📋'
        END,
        'severity', CASE
            WHEN risk_percent > 70 THEN 'red-500'
            WHEN risk_percent > 40 THEN 'yellow-500'
            ELSE 'accent'
        END
    ))
);

-- =============================================================================
-- EXTENDED TOOL SCHEMAS
-- =============================================================================

CREATE OR REPLACE MACRO dev_org_apps_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'open_vibe_coder',
            'description', 'Open smart code generation UI',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'context', json_object('type', 'array', 'items', json_object('type', 'string')),
                'code', json_object('type', 'string'),
                'prompt', json_object('type', 'string')
            ), 'required', json_array('prompt'))
        )),
        json_object('type', 'function', 'function', json_object(
            'name', 'vibe_generate',
            'description', 'Generate code with mode (code/refactor/test/docs)',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'mode', json_object('type', 'string', 'enum', json_array('code', 'refactor', 'test', 'docs')),
                'prompt', json_object('type', 'string'),
                'files', json_object('type', 'array')
            ), 'required', json_array('mode', 'prompt'))
        ))
    )
);

CREATE OR REPLACE MACRO ops_org_apps_tools_schema() AS (
    SELECT json_array(
        json_object('type', 'function', 'function', json_object(
            'name', 'open_terminal',
            'description', 'Open terminal interface',
            'parameters', json_object('type', 'object', 'properties', json_object(
                'cwd', json_object('type', 'string'),
                'output', json_object('type', 'array')
            ))
        ))
    )
);
