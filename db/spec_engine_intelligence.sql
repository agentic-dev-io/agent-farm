-- ============================================================================
-- Spec Engine Intelligence Layer
-- ============================================================================
-- RAG/Embeddings infrastructure using VSS + FTS + DuckLake
-- Provides semantic memory and hybrid retrieval for all organizations.
-- ============================================================================

-- ============================================================================
-- 1. Embedding Storage Tables
-- ============================================================================

-- Central embedding store for all content types
CREATE TABLE IF NOT EXISTS spec_embeddings (
    id              INTEGER PRIMARY KEY,
    spec_id         INTEGER,                    -- Reference to spec_objects (optional)
    org_id          INTEGER,                    -- Reference to org spec
    content_type    VARCHAR NOT NULL,           -- 'code', 'doc', 'decision', 'research', 'design', 'log'
    content_hash    VARCHAR NOT NULL,           -- SHA256 of content for dedup
    content         VARCHAR NOT NULL,           -- Original text content
    chunk_index     INTEGER DEFAULT 0,          -- For chunked documents
    embedding       FLOAT[],                    -- Vector embedding (dimensions depend on model)
    embedding_model VARCHAR DEFAULT 'default',  -- Model used for embedding
    metadata        VARCHAR,                    -- JSON metadata
    created_at      TIMESTAMP DEFAULT current_timestamp,
    updated_at      TIMESTAMP DEFAULT current_timestamp,
    UNIQUE (content_hash, chunk_index)
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_embeddings_spec ON spec_embeddings(spec_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_org ON spec_embeddings(org_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_type ON spec_embeddings(content_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_hash ON spec_embeddings(content_hash);

-- ============================================================================
-- 2. Organization-Specific Knowledge Bases
-- ============================================================================

-- DevOrg: Code embeddings and AST metadata
CREATE TABLE IF NOT EXISTS knowledge_dev (
    id              INTEGER PRIMARY KEY,
    repo            VARCHAR NOT NULL,
    file_path       VARCHAR NOT NULL,
    language        VARCHAR,
    ast_type        VARCHAR,                    -- 'function', 'class', 'module', 'block'
    symbol_name     VARCHAR,                    -- Function/class name
    content         VARCHAR NOT NULL,
    embedding       FLOAT[],
    doc_string      VARCHAR,
    dependencies    VARCHAR[],                  -- Import/require references
    version_ref     VARCHAR,                    -- Git commit/tag
    created_at      TIMESTAMP DEFAULT current_timestamp,
    UNIQUE (repo, file_path, symbol_name, version_ref)
);

-- ResearchOrg: Web search results and summaries
CREATE TABLE IF NOT EXISTS knowledge_research (
    id              INTEGER PRIMARY KEY,
    query           VARCHAR NOT NULL,           -- Original search query
    source_url      VARCHAR,
    source_title    VARCHAR,
    content         VARCHAR NOT NULL,           -- Extracted/summarized text
    embedding       FLOAT[],
    relevance_score REAL,
    search_engine   VARCHAR DEFAULT 'searxng',  -- 'searxng', 'brave', 'duckduckgo'
    search_date     TIMESTAMP DEFAULT current_timestamp,
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- StudioOrg: Design decisions and creative content
CREATE TABLE IF NOT EXISTS knowledge_studio (
    id              INTEGER PRIMARY KEY,
    project         VARCHAR NOT NULL,
    decision_type   VARCHAR NOT NULL,           -- 'design', 'ux', 'copy', 'visual', 'architecture'
    title           VARCHAR NOT NULL,
    description     VARCHAR,
    content         VARCHAR NOT NULL,
    embedding       FLOAT[],
    options         VARCHAR,                    -- JSON array of alternatives considered
    chosen_option   VARCHAR,
    rationale       VARCHAR,
    user_feedback   VARCHAR,                    -- JSON feedback data
    performance     REAL,                       -- Measured success (0.0 - 1.0)
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- OpsOrg: Pipeline runs, logs, and infrastructure state
CREATE TABLE IF NOT EXISTS knowledge_ops (
    id              INTEGER PRIMARY KEY,
    pipeline        VARCHAR NOT NULL,
    run_id          VARCHAR,
    status          VARCHAR,                    -- 'success', 'failed', 'running'
    log_level       VARCHAR DEFAULT 'info',     -- 'debug', 'info', 'warn', 'error'
    content         VARCHAR NOT NULL,
    embedding       FLOAT[],
    artifact_refs   VARCHAR[],                  -- Paths to related artifacts
    metrics         VARCHAR,                    -- JSON metrics data
    duration_ms     INTEGER,
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- ============================================================================
-- 3. Conversation/Session Memory
-- ============================================================================

-- Long-term conversation memory with embeddings
CREATE TABLE IF NOT EXISTS memory_conversations (
    id              INTEGER PRIMARY KEY,
    session_id      VARCHAR NOT NULL,
    agent_spec_id   INTEGER,                    -- Reference to agent spec
    role            VARCHAR NOT NULL,           -- 'user', 'assistant', 'system', 'tool'
    content         VARCHAR NOT NULL,
    embedding       FLOAT[],
    tool_calls      VARCHAR,                    -- JSON tool calls if any
    token_count     INTEGER,
    importance      REAL DEFAULT 0.5,           -- For memory prioritization
    created_at      TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_conversations(agent_spec_id);

-- ============================================================================
-- 4. Sequences
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS spec_embeddings_seq START 1;
CREATE SEQUENCE IF NOT EXISTS knowledge_dev_seq START 1;
CREATE SEQUENCE IF NOT EXISTS knowledge_research_seq START 1;
CREATE SEQUENCE IF NOT EXISTS knowledge_studio_seq START 1;
CREATE SEQUENCE IF NOT EXISTS knowledge_ops_seq START 1;
CREATE SEQUENCE IF NOT EXISTS memory_conversations_seq START 1;

-- ============================================================================
-- 5. Views for Easy Access
-- ============================================================================

-- Recent embeddings by org
CREATE OR REPLACE VIEW recent_embeddings_by_org AS
SELECT
    org_id,
    content_type,
    COUNT(*) as count,
    MAX(created_at) as last_updated
FROM spec_embeddings
GROUP BY org_id, content_type
ORDER BY last_updated DESC;

-- Knowledge base stats
CREATE OR REPLACE VIEW knowledge_stats AS
SELECT 'dev' as org, COUNT(*) as entries FROM knowledge_dev
UNION ALL
SELECT 'research' as org, COUNT(*) as entries FROM knowledge_research
UNION ALL
SELECT 'studio' as org, COUNT(*) as entries FROM knowledge_studio
UNION ALL
SELECT 'ops' as org, COUNT(*) as entries FROM knowledge_ops;
