-- ============================================================================
-- Spec Engine Unified Schema v2.0
-- ============================================================================
-- The Spec Engine is the central "Spec-OS" for all agents.
-- This schema manages ALL specifications: agents, skills, workflows,
-- APIs/protocols, JSON schemas, templates, MCP servers, and more.
--
-- NEW in v2.0:
-- - Provenance tracking (where specs come from, upstream URLs, sync status)
-- - Meta-learning tables (adaptations, feedback, relationships)
-- - Self-improvement tracking
-- ============================================================================

-- Drop existing tables if they exist (clean slate - no backwards compatibility)
DROP TABLE IF EXISTS spec_learning CASCADE;
DROP TABLE IF EXISTS spec_adaptations CASCADE;
DROP TABLE IF EXISTS spec_feedback CASCADE;
DROP TABLE IF EXISTS spec_relationships CASCADE;
DROP TABLE IF EXISTS spec_payloads CASCADE;
DROP TABLE IF EXISTS spec_docs CASCADE;
DROP TABLE IF EXISTS spec_objects CASCADE;

-- ============================================================================
-- Core Spec Tables
-- ============================================================================

-- Main specification objects table with provenance tracking
CREATE TABLE spec_objects (
    id          INTEGER PRIMARY KEY,
    kind        VARCHAR NOT NULL,   -- 'agent', 'skill', 'api', 'protocol', 'schema',
                                    -- 'open_response', 'ui', 'workflow', 'task_template',
                                    -- 'prompt_template', 'tool', 'org', 'mcp_server'
    name        VARCHAR NOT NULL,
    version     VARCHAR NOT NULL DEFAULT '1.0.0',
    status      VARCHAR NOT NULL DEFAULT 'draft',  -- 'draft', 'active', 'deprecated', 'learning'
    summary     VARCHAR NOT NULL,

    -- Provenance: Where does this spec come from?
    source_type VARCHAR DEFAULT 'internal',         -- 'internal', 'upstream', 'learned', 'user', 'mcp'
    source_url  VARCHAR,                            -- URL/URI of original source (e.g., GitHub, npm, spec.modelcontextprotocol.io)
    source_ref  VARCHAR,                            -- Commit hash, version tag, or other reference
    upstream_version VARCHAR,                       -- Version in upstream source
    last_sync   TIMESTAMP,                          -- When was this last synced with upstream?
    sync_status VARCHAR DEFAULT 'none',             -- 'none', 'synced', 'outdated', 'conflict', 'diverged'

    -- Learning metadata
    confidence  REAL DEFAULT 1.0,                   -- Confidence score (0.0 - 1.0) for learned specs
    use_count   INTEGER DEFAULT 0,                  -- How many times has this spec been used?
    success_rate REAL DEFAULT 0.0,                  -- Success rate when used (0.0 - 1.0)

    created_at  TIMESTAMP DEFAULT current_timestamp,
    updated_at  TIMESTAMP DEFAULT current_timestamp,

    -- Ensure unique name+version per kind
    UNIQUE (kind, name, version)
);

-- Documentation for spec objects
CREATE TABLE spec_docs (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,   -- References spec_objects(id)
    doc         VARCHAR NOT NULL,
    doc_format  VARCHAR DEFAULT 'markdown',  -- 'markdown', 'plaintext', 'html'
    created_at  TIMESTAMP DEFAULT current_timestamp
);

-- Payloads (JSON data) for spec objects
CREATE TABLE spec_payloads (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL,   -- References spec_objects(id)
    payload     VARCHAR,            -- JSON stored as VARCHAR for compatibility
    schema_ref  VARCHAR,            -- Optional: reference to a 'schema' spec for validation
    created_at  TIMESTAMP DEFAULT current_timestamp
);

-- ============================================================================
-- Relationship Tracking (Links between specs)
-- ============================================================================

-- Track relationships between specs (e.g., agent uses skill, workflow includes steps)
CREATE TABLE spec_relationships (
    id          INTEGER PRIMARY KEY,
    from_id     INTEGER NOT NULL,   -- Source spec
    to_id       INTEGER NOT NULL,   -- Target spec
    rel_type    VARCHAR NOT NULL,   -- 'uses', 'extends', 'requires', 'implements', 'derived_from'
    metadata    VARCHAR,            -- Optional JSON metadata about the relationship
    created_at  TIMESTAMP DEFAULT current_timestamp,
    UNIQUE (from_id, to_id, rel_type)
);

-- ============================================================================
-- Meta-Learning Tables (Self-Improvement System)
-- ============================================================================

-- Track feedback on spec usage (for learning)
CREATE TABLE spec_feedback (
    id          INTEGER PRIMARY KEY,
    spec_id     INTEGER NOT NULL,   -- Which spec received feedback
    session_id  VARCHAR,            -- Session where feedback was given
    feedback_type VARCHAR NOT NULL, -- 'success', 'failure', 'timeout', 'error', 'user_correction'
    context     VARCHAR,            -- JSON context of the usage
    outcome     VARCHAR,            -- JSON outcome/result
    score       REAL,               -- Numeric score (-1.0 to 1.0)
    notes       VARCHAR,            -- Human-readable notes
    created_at  TIMESTAMP DEFAULT current_timestamp
);

-- Track adaptations/improvements made to specs
CREATE TABLE spec_adaptations (
    id              INTEGER PRIMARY KEY,
    spec_id         INTEGER NOT NULL,       -- Original spec being adapted
    adapted_spec_id INTEGER,                -- New adapted version (if created)
    adaptation_type VARCHAR NOT NULL,       -- 'parameter_tune', 'prompt_improve', 'tool_add', 'merge', 'split'
    reason          VARCHAR NOT NULL,       -- Why was this adaptation made?
    changes         VARCHAR NOT NULL,       -- JSON describing the changes
    metrics_before  VARCHAR,                -- JSON metrics before adaptation
    metrics_after   VARCHAR,                -- JSON metrics after adaptation
    approved        BOOLEAN DEFAULT FALSE,  -- Has this adaptation been approved?
    approved_by     VARCHAR,                -- Who approved it?
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- Track overall learning patterns and insights
CREATE TABLE spec_learning (
    id              INTEGER PRIMARY KEY,
    learning_type   VARCHAR NOT NULL,       -- 'pattern', 'insight', 'rule', 'preference'
    category        VARCHAR NOT NULL,       -- 'agent', 'skill', 'workflow', 'general'
    description     VARCHAR NOT NULL,       -- What was learned?
    evidence        VARCHAR,                -- JSON array of evidence (spec_ids, feedback_ids)
    confidence      REAL DEFAULT 0.5,       -- Confidence in this learning (0.0 - 1.0)
    application     VARCHAR,                -- How should this be applied?
    created_at      TIMESTAMP DEFAULT current_timestamp,
    last_applied    TIMESTAMP
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Core spec indexes
CREATE INDEX idx_spec_objects_kind ON spec_objects(kind);
CREATE INDEX idx_spec_objects_name ON spec_objects(name);
CREATE INDEX idx_spec_objects_status ON spec_objects(status);
CREATE INDEX idx_spec_objects_kind_name ON spec_objects(kind, name);
CREATE INDEX idx_spec_objects_source_type ON spec_objects(source_type);
CREATE INDEX idx_spec_objects_sync_status ON spec_objects(sync_status);
CREATE INDEX idx_spec_docs_object_id ON spec_docs(object_id);
CREATE INDEX idx_spec_payloads_object_id ON spec_payloads(object_id);

-- Relationship indexes
CREATE INDEX idx_spec_relationships_from ON spec_relationships(from_id);
CREATE INDEX idx_spec_relationships_to ON spec_relationships(to_id);
CREATE INDEX idx_spec_relationships_type ON spec_relationships(rel_type);

-- Learning indexes
CREATE INDEX idx_spec_feedback_spec ON spec_feedback(spec_id);
CREATE INDEX idx_spec_feedback_type ON spec_feedback(feedback_type);
CREATE INDEX idx_spec_adaptations_spec ON spec_adaptations(spec_id);
CREATE INDEX idx_spec_learning_type ON spec_learning(learning_type);
CREATE INDEX idx_spec_learning_category ON spec_learning(category);

-- ============================================================================
-- Convenience Views by Kind
-- ============================================================================

-- Agents view
CREATE OR REPLACE VIEW spec_agents_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'agent';

-- Skills view
CREATE OR REPLACE VIEW spec_skills_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'skill';

-- APIs view
CREATE OR REPLACE VIEW spec_apis_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'api';

-- Protocols view
CREATE OR REPLACE VIEW spec_protocols_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'protocol';

-- Schemas view (JSON Schemas for validation)
CREATE OR REPLACE VIEW spec_schemas_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'schema';

-- Task templates view
CREATE OR REPLACE VIEW spec_task_templates_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'task_template';

-- Prompt templates view
CREATE OR REPLACE VIEW spec_prompt_templates_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'prompt_template';

-- Tools view
CREATE OR REPLACE VIEW spec_tools_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'tool';

-- Workflows view
CREATE OR REPLACE VIEW spec_workflows_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'workflow';

-- UIs / Open Responses view
CREATE OR REPLACE VIEW spec_ui_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind IN ('ui', 'open_response');

-- Organizations view
CREATE OR REPLACE VIEW spec_orgs_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'org';

-- MCP Servers view
CREATE OR REPLACE VIEW spec_mcp_servers_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.source_type, o.source_url, o.sync_status,
    o.created_at, o.updated_at,
    d.doc,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id
WHERE o.kind = 'mcp_server';

-- ============================================================================
-- Full Spec View (all specs with docs and payloads)
-- ============================================================================

CREATE OR REPLACE VIEW spec_full_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status, o.summary,
    o.source_type, o.source_url, o.source_ref, o.upstream_version,
    o.last_sync, o.sync_status,
    o.confidence, o.use_count, o.success_rate,
    o.created_at, o.updated_at,
    d.doc,
    d.doc_format,
    p.payload,
    p.schema_ref
FROM spec_objects o
LEFT JOIN spec_docs d ON d.object_id = o.id
LEFT JOIN spec_payloads p ON p.object_id = o.id;

-- ============================================================================
-- Provenance Views
-- ============================================================================

-- Specs from upstream sources (need syncing)
CREATE OR REPLACE VIEW spec_upstream_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status,
    o.source_type, o.source_url, o.source_ref, o.upstream_version,
    o.last_sync, o.sync_status,
    o.summary
FROM spec_objects o
WHERE o.source_type = 'upstream'
ORDER BY o.sync_status DESC, o.last_sync ASC;

-- Learned specs (from meta-learning)
CREATE OR REPLACE VIEW spec_learned_view AS
SELECT
    o.id, o.kind, o.name, o.version, o.status,
    o.confidence, o.use_count, o.success_rate,
    o.summary,
    o.created_at
FROM spec_objects o
WHERE o.source_type = 'learned'
ORDER BY o.confidence DESC, o.use_count DESC;

-- ============================================================================
-- Meta-Learning Views
-- ============================================================================

-- Spec performance summary
CREATE OR REPLACE VIEW spec_performance_view AS
SELECT
    o.id, o.kind, o.name, o.version,
    o.use_count,
    o.success_rate,
    COUNT(f.id) AS feedback_count,
    AVG(f.score) AS avg_feedback_score,
    COUNT(f.id) FILTER (WHERE f.feedback_type = 'success') AS success_count,
    COUNT(f.id) FILTER (WHERE f.feedback_type = 'failure') AS failure_count
FROM spec_objects o
LEFT JOIN spec_feedback f ON f.spec_id = o.id
GROUP BY o.id, o.kind, o.name, o.version, o.use_count, o.success_rate
ORDER BY o.use_count DESC;

-- Relationship graph view
CREATE OR REPLACE VIEW spec_graph_view AS
SELECT
    r.id AS rel_id,
    r.rel_type,
    f.id AS from_id, f.kind AS from_kind, f.name AS from_name,
    t.id AS to_id, t.kind AS to_kind, t.name AS to_name,
    r.metadata
FROM spec_relationships r
JOIN spec_objects f ON f.id = r.from_id
JOIN spec_objects t ON t.id = r.to_id;

-- Recent adaptations view
CREATE OR REPLACE VIEW spec_adaptations_view AS
SELECT
    a.id, a.adaptation_type, a.reason,
    o.kind AS spec_kind, o.name AS spec_name,
    a.changes,
    a.approved, a.approved_by,
    a.created_at
FROM spec_adaptations a
JOIN spec_objects o ON o.id = a.spec_id
ORDER BY a.created_at DESC;

-- Learning insights view
CREATE OR REPLACE VIEW spec_insights_view AS
SELECT
    l.id, l.learning_type, l.category,
    l.description, l.confidence,
    l.application,
    l.created_at, l.last_applied
FROM spec_learning l
WHERE l.confidence >= 0.5
ORDER BY l.confidence DESC, l.created_at DESC;

-- ============================================================================
-- Sequences for auto-incrementing IDs
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS spec_objects_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_docs_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_payloads_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_relationships_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_feedback_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_adaptations_seq START 1;
CREATE SEQUENCE IF NOT EXISTS spec_learning_seq START 1;
