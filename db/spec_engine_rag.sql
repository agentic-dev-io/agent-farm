-- ============================================================================
-- Spec Engine RAG (Retrieval Augmented Generation) Macros
-- ============================================================================
-- Hybrid search combining Vector Similarity (VSS) + Full-Text Search (FTS)
-- for intelligent retrieval across all knowledge bases.
-- ============================================================================

-- ============================================================================
-- A) Vector Similarity Search Macros (VSS)
-- ============================================================================

-- Search embeddings by vector similarity
-- Usage: SELECT * FROM vss_search_embeddings(query_embedding, 10, 'code');
CREATE OR REPLACE MACRO vss_search_embeddings(query_vec, k, content_type_filter) AS TABLE (
    SELECT
        id, spec_id, org_id, content_type,
        content, metadata,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM spec_embeddings
    WHERE content_type = content_type_filter
      AND embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- Search all embeddings regardless of type
-- Usage: SELECT * FROM vss_search_all(query_embedding, 20);
CREATE OR REPLACE MACRO vss_search_all(query_vec, k) AS TABLE (
    SELECT
        id, spec_id, org_id, content_type,
        content, metadata,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM spec_embeddings
    WHERE embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- Search DevOrg code knowledge
-- Usage: SELECT * FROM vss_search_code(query_embedding, 10, 'python');
CREATE OR REPLACE MACRO vss_search_code(query_vec, k, lang_filter) AS TABLE (
    SELECT
        id, repo, file_path, language, ast_type, symbol_name,
        content, doc_string,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM knowledge_dev
    WHERE (lang_filter IS NULL OR language = lang_filter)
      AND embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- Search ResearchOrg knowledge
-- Usage: SELECT * FROM vss_search_research(query_embedding, 10);
CREATE OR REPLACE MACRO vss_search_research(query_vec, k) AS TABLE (
    SELECT
        id, query, source_url, source_title,
        content, relevance_score,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM knowledge_research
    WHERE embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- Search StudioOrg decisions
-- Usage: SELECT * FROM vss_search_decisions(query_embedding, 10, 'design');
CREATE OR REPLACE MACRO vss_search_decisions(query_vec, k, decision_type_filter) AS TABLE (
    SELECT
        id, project, decision_type, title,
        description, content, rationale, performance,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM knowledge_studio
    WHERE (decision_type_filter IS NULL OR decision_type = decision_type_filter)
      AND embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- Search conversation memory
-- Usage: SELECT * FROM vss_search_memory(query_embedding, 10, 'session-123');
CREATE OR REPLACE MACRO vss_search_memory(query_vec, k, session_filter) AS TABLE (
    SELECT
        id, session_id, role, content, importance,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM memory_conversations
    WHERE (session_filter IS NULL OR session_id = session_filter)
      AND embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- ============================================================================
-- B) Hybrid Search Macros (VSS + FTS)
-- ============================================================================

-- Hybrid search combining keyword match with vector similarity
-- Usage: SELECT * FROM hybrid_search_embeddings(query_text, query_embedding, 10, 'doc');
CREATE OR REPLACE MACRO hybrid_search_embeddings(text_query, query_vec, k, content_type_filter) AS TABLE (
    WITH keyword_matches AS (
        SELECT id, 1.0 AS keyword_score
        FROM spec_embeddings
        WHERE content_type = content_type_filter
          AND content ILIKE '%' || text_query || '%'
    ),
    vector_matches AS (
        SELECT
            id,
            array_cosine_similarity(embedding, query_vec) AS vector_score
        FROM spec_embeddings
        WHERE content_type = content_type_filter
          AND embedding IS NOT NULL
    )
    SELECT
        e.id, e.spec_id, e.org_id, e.content_type,
        e.content, e.metadata,
        COALESCE(k.keyword_score, 0) AS keyword_score,
        COALESCE(v.vector_score, 0) AS vector_score,
        (COALESCE(k.keyword_score, 0) * 0.3 + COALESCE(v.vector_score, 0) * 0.7) AS hybrid_score
    FROM spec_embeddings e
    LEFT JOIN keyword_matches k ON k.id = e.id
    LEFT JOIN vector_matches v ON v.id = e.id
    WHERE e.content_type = content_type_filter
      AND (k.id IS NOT NULL OR v.id IS NOT NULL)
    ORDER BY hybrid_score DESC
    LIMIT k
);

-- Hybrid search across all knowledge bases
-- Usage: SELECT * FROM hybrid_search_all(query_text, query_embedding, 20);
CREATE OR REPLACE MACRO hybrid_search_all(text_query, query_vec, k) AS TABLE (
    WITH keyword_matches AS (
        SELECT id, 'embeddings' as source, 1.0 AS keyword_score
        FROM spec_embeddings
        WHERE content ILIKE '%' || text_query || '%'
    ),
    vector_matches AS (
        SELECT
            id, 'embeddings' as source,
            array_cosine_similarity(embedding, query_vec) AS vector_score
        FROM spec_embeddings
        WHERE embedding IS NOT NULL
    )
    SELECT
        e.id, e.content_type as source_type,
        e.content,
        COALESCE(k.keyword_score, 0) AS keyword_score,
        COALESCE(v.vector_score, 0) AS vector_score,
        (COALESCE(k.keyword_score, 0) * 0.3 + COALESCE(v.vector_score, 0) * 0.7) AS hybrid_score
    FROM spec_embeddings e
    LEFT JOIN keyword_matches k ON k.id = e.id
    LEFT JOIN vector_matches v ON v.id = e.id
    WHERE k.id IS NOT NULL OR v.id IS NOT NULL
    ORDER BY hybrid_score DESC
    LIMIT k
);

-- ============================================================================
-- C) Context Building Macros (for RAG prompts)
-- ============================================================================

-- Build context from search results
-- Usage: SELECT build_rag_context(query_embedding, 5, 'code');
CREATE OR REPLACE MACRO build_rag_context(query_vec, k, content_type_filter) AS (
    SELECT string_agg(content, E'\n\n---\n\n') AS context
    FROM (
        SELECT content
        FROM spec_embeddings
        WHERE content_type = content_type_filter
          AND embedding IS NOT NULL
        ORDER BY array_cosine_similarity(embedding, query_vec) DESC
        LIMIT k
    )
);

-- Get relevant specs for a query
-- Usage: SELECT * FROM rag_relevant_specs(query_embedding, 5);
CREATE OR REPLACE MACRO rag_relevant_specs(query_vec, k) AS TABLE (
    SELECT DISTINCT
        s.id, s.kind, s.name, s.version, s.summary,
        MAX(array_cosine_similarity(e.embedding, query_vec)) AS max_similarity
    FROM spec_embeddings e
    JOIN spec_objects s ON s.id = e.spec_id
    WHERE e.embedding IS NOT NULL
      AND e.spec_id IS NOT NULL
    GROUP BY s.id, s.kind, s.name, s.version, s.summary
    ORDER BY max_similarity DESC
    LIMIT k
);

-- ============================================================================
-- D) Memory Management Macros
-- ============================================================================

-- Get recent conversation context with importance weighting
-- Usage: SELECT * FROM get_conversation_context('session-123', 10);
CREATE OR REPLACE MACRO get_conversation_context(session_id_val, k) AS TABLE (
    SELECT
        role, content, importance, created_at
    FROM memory_conversations
    WHERE session_id = session_id_val
    ORDER BY
        importance DESC,
        created_at DESC
    LIMIT k
);

-- Get similar past conversations
-- Usage: SELECT * FROM find_similar_conversations(query_embedding, 5);
CREATE OR REPLACE MACRO find_similar_conversations(query_vec, k) AS TABLE (
    SELECT
        session_id,
        role,
        content,
        importance,
        array_cosine_similarity(embedding, query_vec) AS similarity
    FROM memory_conversations
    WHERE embedding IS NOT NULL
    ORDER BY similarity DESC
    LIMIT k
);

-- ============================================================================
-- E) Knowledge Base Statistics
-- ============================================================================

-- Get embedding coverage stats
-- Usage: SELECT * FROM embedding_coverage();
CREATE OR REPLACE MACRO embedding_coverage() AS TABLE (
    SELECT
        content_type,
        COUNT(*) AS total_entries,
        COUNT(embedding) AS with_embeddings,
        ROUND(COUNT(embedding) * 100.0 / COUNT(*), 2) AS coverage_pct
    FROM spec_embeddings
    GROUP BY content_type
    ORDER BY content_type
);

-- Get knowledge freshness
-- Usage: SELECT * FROM knowledge_freshness();
CREATE OR REPLACE MACRO knowledge_freshness() AS TABLE (
    SELECT
        'dev' AS org,
        COUNT(*) AS entries,
        MAX(created_at) AS last_update,
        COUNT(*) FILTER (WHERE created_at > current_timestamp - INTERVAL '7 days') AS last_7_days
    FROM knowledge_dev
    UNION ALL
    SELECT
        'research' AS org,
        COUNT(*) AS entries,
        MAX(created_at) AS last_update,
        COUNT(*) FILTER (WHERE created_at > current_timestamp - INTERVAL '7 days') AS last_7_days
    FROM knowledge_research
    UNION ALL
    SELECT
        'studio' AS org,
        COUNT(*) AS entries,
        MAX(created_at) AS last_update,
        COUNT(*) FILTER (WHERE created_at > current_timestamp - INTERVAL '7 days') AS last_7_days
    FROM knowledge_studio
    UNION ALL
    SELECT
        'ops' AS org,
        COUNT(*) AS entries,
        MAX(created_at) AS last_update,
        COUNT(*) FILTER (WHERE created_at > current_timestamp - INTERVAL '7 days') AS last_7_days
    FROM knowledge_ops
);

-- ============================================================================
-- F) DuckLake Integration Helpers
-- ============================================================================

-- These macros help with DuckLake time-travel and snapshot features
-- Note: Actual DuckLake catalog setup requires external configuration

-- Placeholder for time-travel query (DuckLake syntax)
-- Usage: SELECT * FROM knowledge_at_time('knowledge_dev', '2024-01-15');
CREATE OR REPLACE MACRO knowledge_at_time(table_name, as_of_date) AS (
    -- When DuckLake is configured, this would use:
    -- SELECT * FROM ducklake.catalog.{table_name} FOR SYSTEM_TIME AS OF {as_of_date}
    SELECT 'DuckLake time-travel requires catalog configuration' AS note
);

-- Get embedding model stats
-- Usage: SELECT * FROM embedding_model_stats();
CREATE OR REPLACE MACRO embedding_model_stats() AS TABLE (
    SELECT
        embedding_model,
        COUNT(*) AS embeddings_count,
        MIN(created_at) AS first_used,
        MAX(created_at) AS last_used
    FROM spec_embeddings
    WHERE embedding IS NOT NULL
    GROUP BY embedding_model
    ORDER BY embeddings_count DESC
);
