"""
Organization configurations for multi-agent system.

Defines 5 organizations with their models, tools, workspaces, and restrictions.
"""

from .schemas import OrgType, SecurityProfile, WorkspaceMode

# =============================================================================
# ORGANIZATION CONFIGURATIONS
# =============================================================================

ORG_CONFIGS = {
    # -------------------------------------------------------------------------
    # DevOrg - Development / Pipelines-as-Code
    # -------------------------------------------------------------------------
    OrgType.DEV: {
        "id": "dev-org",
        "name": "DevOrg",
        "description": "Entwicklung, Code-Reviews, Pipeline-Konfigurationen",
        "model_primary": "glm-4.7:cloud",
        "model_secondary": "qwen3-coder:cloud",
        "security_profile": SecurityProfile.STANDARD,
        "workspaces": [
            {"path": "/projects/dev", "mode": WorkspaceMode.WRITER, "name": "Development"},
        ],
        "tools": [
            "fs_read",
            "fs_write",
            "fs_list",
            "git_status",
            "git_diff",
            "git_patch",
            "test_run",
            # Smart Extensions (JSONata)
            "json_transform",
            "dev_validate_config",
            "dev_extract_deps",
        ],
        "tools_requiring_approval": ["fs_write", "git_patch"],
        "denials": [
            ("shell", "*", "Shell-Zugriff ist für DevOrg nicht erlaubt"),
            ("workspace", "/projects/ops/*", "Kein Zugriff auf Ops-Workspace"),
            ("workspace", "/projects/studio/*", "Kein Zugriff auf Studio-Workspace"),
            ("tool", "ci_trigger", "CI/CD-Trigger nicht erlaubt"),
            ("tool", "deploy_service", "Deployments nicht erlaubt"),
        ],
    },
    # -------------------------------------------------------------------------
    # OpsOrg - Operations / CI/CD & Render-Ausführung
    # -------------------------------------------------------------------------
    OrgType.OPS: {
        "id": "ops-org",
        "name": "OpsOrg",
        "description": "CI/CD-Pipelines, Deployments, Render-Jobs",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "minimax-m2.1:cloud",
        "security_profile": SecurityProfile.POWER,
        "workspaces": [
            {"path": "/projects/ops", "mode": WorkspaceMode.WRITER, "name": "Operations"},
        ],
        "tools": [
            "fs_read",
            "fs_list",
            "ci_trigger",
            "deploy_service",
            "rollback_service",
            "render_job_submit",
            "render_job_status",
            "shell_run",
            # Smart Extensions (Bitfilters + Radio)
            "ops_is_duplicate",
            "ops_add_to_filter",
            "ops_subscribe_ci",
            "ops_publish_status",
        ],
        "tools_requiring_approval": [
            "deploy_service",
            "rollback_service",
            "shell_run",
        ],
        "shell_allowlist": [
            "kubectl",
            "docker",
            "systemctl status",
            "journalctl",
            "df",
            "free",
            "top -b -n 1",
        ],
        "denials": [
            ("workspace", "/projects/dev/*", "Kein Schreibzugriff auf Dev-Repos"),
            ("tool", "fs_write", "Code-Änderungen nur über DevOrg"),
            ("tool", "git_patch", "Code-Änderungen nur über DevOrg"),
        ],
    },
    # -------------------------------------------------------------------------
    # ResearchOrg - Recherche via SearXNG
    # -------------------------------------------------------------------------
    OrgType.RESEARCH: {
        "id": "research-org",
        "name": "ResearchOrg",
        "description": "Externe Recherche, Zusammenfassungen, Research-Notes",
        "model_primary": "gpt-oss:20b-cloud",
        "model_secondary": "minimax-m2.1:cloud",
        "security_profile": SecurityProfile.CONSERVATIVE,
        "workspaces": [
            {"path": "/data/research", "mode": WorkspaceMode.WRITER, "name": "Research Notes"},
        ],
        "tools": [
            "searxng_search",
            "fs_read",
            "fs_write_note",
            "fs_list_notes",
            # Smart Extensions (JSONata + Lindel + LSH)
            "json_transform",
            "research_parse_api",
            "research_normalize_results",
            "research_encode_embedding",
            "research_decode_embedding",
            "research_fingerprint",
            "research_find_duplicates",
            "research_minhash_signature",
            "research_index_doc",
            "research_find_similar_docs",
        ],
        "tools_requiring_approval": [],
        "searxng_endpoint": "http://searxng:8080",
        "denials": [
            ("tool", "fetch", "Direkter HTTP-Zugriff nicht erlaubt"),
            ("tool", "fetch_url", "Direkter HTTP-Zugriff nicht erlaubt"),
            ("tool", "shell_run", "Shell-Zugriff nicht erlaubt"),
            ("tool", "deploy_service", "Deployments nicht erlaubt"),
            ("workspace", "/projects/*", "Kein Zugriff auf Projekt-Workspaces"),
        ],
    },
    # -------------------------------------------------------------------------
    # StudioOrg - Product / Creative / DCC-Briefings
    # -------------------------------------------------------------------------
    OrgType.STUDIO: {
        "id": "studio-org",
        "name": "StudioOrg",
        "description": "Anforderungen, Specs, DCC-Briefings, Shot-Notes",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "gemma3:4b-cloud",
        "security_profile": SecurityProfile.STANDARD,
        "workspaces": [
            {"path": "/projects/studio", "mode": WorkspaceMode.WRITER, "name": "Studio"},
        ],
        "tools": [
            "fs_read",
            "fs_write",
            "fs_list",
            "notes_board_create",
            "notes_board_list",
            "notes_board_update",
            # Smart Extensions (Lindel + Radio)
            "studio_index_asset",
            "studio_find_similar",
            "studio_asset_order",
            "studio_collab_event",
        ],
        "tools_requiring_approval": [],
        "denials": [
            ("workspace", "/projects/dev/*", "Kein Zugriff auf Dev-Workspace"),
            ("workspace", "/projects/ops/*", "Kein Zugriff auf Ops-Workspace"),
            ("tool", "shell_run", "Shell-Zugriff nicht erlaubt"),
            ("tool", "ci_trigger", "CI/CD nicht erlaubt"),
            ("tool", "deploy_service", "Deployments nicht erlaubt"),
            ("pattern", "*.py", "Keine Python-Dateien bearbeiten"),
            ("pattern", "*.sh", "Keine Shell-Skripte bearbeiten"),
            ("pattern", "*.yaml", "Keine Pipeline-Configs bearbeiten"),
        ],
    },
    # -------------------------------------------------------------------------
    # OrchestratorOrg - Zentrale Steuerung
    # -------------------------------------------------------------------------
    OrgType.ORCHESTRATOR: {
        "id": "orchestrator-org",
        "name": "OrchestratorOrg",
        "description": "Zentrale Aufgabenverteilung an Orgs",
        "model_primary": "kimi-k2.5:cloud",
        "model_secondary": "glm-4.7:cloud",
        "security_profile": SecurityProfile.CONSERVATIVE,
        "workspaces": [],  # Kein direkter Workspace-Zugriff
        "tools": [
            "call_dev_org",
            "call_ops_org",
            "call_research_org",
            "call_studio_org",
            # Smart Extensions (DuckPGQ + Radio)
            "orchestrator_call_chain",
            "orchestrator_add_dependency",
            "orchestrator_get_ready_tasks",
            "orchestrator_broadcast",
            "orchestrator_listen",
            "orchestrator_subscribe",
            "smart_route",
        ],
        "tools_requiring_approval": [],
        "denials": [
            ("tool", "fs_read", "Kein direkter Dateizugriff"),
            ("tool", "fs_write", "Kein direkter Dateizugriff"),
            ("tool", "shell_run", "Kein Shell-Zugriff"),
            ("tool", "fetch", "Kein Web-Zugriff"),
        ],
    },
}

# =============================================================================
# SYSTEM PROMPTS (Deutsch, strikt)
# =============================================================================

ORG_SYSTEM_PROMPTS = {
    OrgType.DEV: """Du bist DevOrg - der Entwicklungs-Agent.

ROLLE:
- Code lesen, schreiben und reviewen
- Pipeline-Konfigurationen (YAML, JSON) erstellen und bearbeiten
- Tests ausführen und Fehler analysieren
- PRs und Code-Vorschläge vorbereiten

ERLAUBTE AKTIONEN:
- Dateien in /projects/dev lesen und schreiben
- Git-Status und Diffs anzeigen
- Patches erstellen
- Lokale Tests ausführen

SMART EXTENSIONS (JSONata):
- json_transform(): JSON-Daten transformieren mit JSONata-Expressions
- dev_validate_config(): Config-Dateien gegen Schema validieren
- dev_extract_deps(): Dependencies aus package.json/pyproject.toml extrahieren

VERBOTEN:
- Shell-Befehle ausführen
- CI/CD-Pipelines triggern
- Deployments durchführen
- Zugriff auf /projects/ops oder /projects/studio
- Produktiv-Systeme direkt ändern

Bei Deployment-Anfragen: Weise auf OpsOrg hin.
Bei Research-Anfragen: Weise auf ResearchOrg hin.""",
    OrgType.OPS: """Du bist OpsOrg - der Operations-Agent.

ROLLE:
- CI/CD-Pipelines ausführen und überwachen
- Deployments und Rollbacks durchführen
- Render-Jobs starten und Status prüfen
- System-Health überwachen

ERLAUBTE AKTIONEN:
- Pipeline-Ausführung triggern
- Services deployen (mit Approval)
- Rollbacks durchführen (mit Approval)
- Render-Jobs verwalten
- Shell-Befehle aus Allowlist (kubectl, docker, systemctl status)
- Logs in /projects/ops schreiben

SMART EXTENSIONS (Bitfilters + Radio):
- ops_is_duplicate(): Prüfen ob Log-Eintrag bereits existiert (Bloom-Filter)
- ops_add_to_filter(): Einträge zum Dedup-Filter hinzufügen
- ops_subscribe_ci(): CI/CD Events in Echtzeit empfangen
- ops_publish_status(): Deployment-Status broadcasten

VERBOTEN:
- Code in Dev-Repos ändern
- Pipeline-Definitionen selbst schreiben (kommt von DevOrg)
- Spontane Skript-Änderungen
- Zugriff auf /projects/dev zum Schreiben

Pipeline-Code muss IMMER aus dem Repo kommen, nie spontan erstellt.""",
    OrgType.RESEARCH: """Du bist ResearchOrg - der Recherche-Agent.

ROLLE:
- Externe Informationen über SearXNG suchen
- Quellen analysieren und zusammenfassen
- Research-Notes schreiben und organisieren
- Dokument-Ähnlichkeit und Duplikate erkennen

ERLAUBTE AKTIONEN:
- SearXNG-Suchen durchführen
- Notes in /data/research schreiben
- Recherche-Ergebnisse strukturieren

SMART EXTENSIONS (JSONata + Lindel + LSH):
- research_parse_api(): API-Responses intelligent parsen
- research_normalize_results(): Suchergebnisse aus verschiedenen Quellen normalisieren
- research_encode_embedding(): Embeddings mit Hilbert-Kurve für schnelle Suche kodieren
- research_index_doc(): Dokumente für Similarity-Search indexieren
- research_find_similar_docs(): Ähnliche Dokumente per MinHash finden
- research_fingerprint(): Text-Fingerprint für Duplikaterkennung

VERBOTEN:
- Direkte HTTP-Requests ins Internet (nur SearXNG)
- Shell-Befehle
- Deployments
- Zugriff auf /projects/* Verzeichnisse
- Code schreiben oder ändern

Alle Web-Zugriffe NUR über searxng_search().
Zitiere immer deine Quellen.""",
    OrgType.STUDIO: """Du bist StudioOrg - der Creative/Product-Agent.

ROLLE:
- Anforderungen und User-Stories schreiben
- Feature-Spezifikationen erstellen
- DCC-Briefings und Shot-Notes verfassen
- Roadmaps und Dokumentation pflegen
- Assets organisieren und verwalten

ERLAUBTE AKTIONEN:
- Dokumente in /projects/studio lesen und schreiben
- Notes-Board verwalten (create/list/update)
- Specs, Briefings, Notizen erstellen

SMART EXTENSIONS (Lindel + Radio):
- studio_index_asset(): Assets mit Feature-Vektoren indexieren
- studio_find_similar(): Ähnliche Assets per Hilbert-Distanz finden
- studio_asset_order(): Assets räumlich clustern (Morton-Encoding)
- studio_collab_event(): Real-time Collaboration Events publishen

VERBOTEN:
- Code-Dateien (*.py, *.sh, *.js) bearbeiten
- Pipeline-Configs (*.yaml, *.yml) ändern
- Shell-Befehle
- Deployments oder CI/CD
- Zugriff auf /projects/dev oder /projects/ops

Du schreibst NUR Dokumentation und Spezifikationen, KEINEN Code.""",
    OrgType.ORCHESTRATOR: """Du bist OrchestratorOrg - der zentrale Koordinator.

ROLLE:
- User-Aufgaben analysieren und in Teilaufgaben zerlegen
- Aufgaben an die passenden Orgs delegieren
- Ergebnisse zusammenführen und präsentieren
- Task-Dependencies verwalten und optimieren

VERFÜGBARE ORGS:
- DevOrg: Code, Pipelines, Tests → call_dev_org()
- OpsOrg: Deployments, CI/CD, Render → call_ops_org()
- ResearchOrg: Web-Recherche, Zusammenfassungen → call_research_org()
- StudioOrg: Specs, Briefings, Dokumentation → call_studio_org()

SMART EXTENSIONS (DuckPGQ + Radio):
- orchestrator_call_chain(): Org-Call-Historie als Graph visualisieren
- orchestrator_add_dependency(): Task-Abhängigkeiten definieren
- orchestrator_get_ready_tasks(): Alle Tasks ohne Blocker finden
- orchestrator_broadcast(): Tasks an Agents broadcasten
- orchestrator_listen(): Auf Agent-Responses warten
- smart_route(): Auto-Route zu passender Extension basierend auf Org+Task

ERLAUBTE AKTIONEN:
- Orgs aufrufen mit klaren Aufgaben
- Ergebnisse zusammenfassen
- Rückfragen stellen
- Task-Graph verwalten

VERBOTEN:
- Direkter Dateizugriff
- Shell-Befehle
- Web-Requests
- Eigene Tool-Ausführung (nur Org-Calls)

Delegiere IMMER an die passende Org. Führe NIE selbst aus.""",
}


def get_org_config(org_type: OrgType) -> dict:
    """Get configuration for an organization."""
    return ORG_CONFIGS.get(org_type, {})


def get_org_prompt(org_type: OrgType) -> str:
    """Get system prompt for an organization."""
    return ORG_SYSTEM_PROMPTS.get(org_type, "")


def get_all_org_ids() -> list[str]:
    """Get all organization IDs."""
    return [cfg["id"] for cfg in ORG_CONFIGS.values()]


# SQL to seed org configurations
def generate_org_seed_sql() -> str:
    """Generate SQL to seed organization configurations."""
    statements = []

    for org_type, config in ORG_CONFIGS.items():
        prompt = ORG_SYSTEM_PROMPTS.get(org_type, "").replace("'", "''")
        desc = config.get("description", "").replace("'", "''")

        statements.append(f"""
INSERT INTO orgs (id, name, org_type, description, model_primary, model_secondary, system_prompt)
VALUES (
    '{config["id"]}',
    '{config["name"]}',
    '{org_type.value}',
    '{desc}',
    '{config["model_primary"]}',
    '{config.get("model_secondary", "")}',
    '{prompt}'
) ON CONFLICT (id) DO UPDATE SET
    model_primary = EXCLUDED.model_primary,
    model_secondary = EXCLUDED.model_secondary,
    system_prompt = EXCLUDED.system_prompt;
""")

        # Tool permissions
        for tool in config.get("tools", []):
            req_approval = tool in config.get("tools_requiring_approval", [])
            statements.append(f"""
INSERT INTO org_tools (org_id, tool_name, enabled, requires_approval)
VALUES ('{config["id"]}', '{tool}', TRUE, {str(req_approval).upper()})
ON CONFLICT (org_id, tool_name) DO UPDATE SET
    enabled = TRUE, requires_approval = {str(req_approval).upper()};
""")

        # Denials
        for denial in config.get("denials", []):
            denial_type, pattern, reason = denial
            reason_escaped = reason.replace("'", "''")
            statements.append(f"""
INSERT INTO org_denials (org_id, denial_type, pattern, reason)
VALUES ('{config["id"]}', '{denial_type}', '{pattern}', '{reason_escaped}')
ON CONFLICT (org_id, denial_type, pattern) DO NOTHING;
""")

    return "\n".join(statements)
