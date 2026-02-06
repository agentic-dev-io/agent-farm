-- 09_smart_extensions.sql - Smart Extension Macros per Organization
-- Makes the system smarter through targeted extension usage

-- =============================================================================
-- JSONATA (ResearchOrg + DevOrg)
-- Powerful JSON transformation and querying
-- =============================================================================

-- Transform JSON with JSONata expression
CREATE OR REPLACE MACRO json_transform(json_data, expression) AS (
    SELECT jsonata(expression, json_data)
);

-- Extract nested data with JSONata path
CREATE OR REPLACE MACRO json_extract_deep(json_data, path_expr) AS (
    SELECT jsonata(path_expr, json_data)
);

-- ResearchOrg: Parse API responses intelligently
CREATE OR REPLACE MACRO research_parse_api(api_response) AS (
    SELECT jsonata(
        -- Extract relevant fields, flatten nested structures
        '{ "title": title, "abstract": abstract, "authors": authors.name, "year": $number(year), "citations": $count(citations) }',
        api_response
    )
);

-- ResearchOrg: Normalize search results from different sources
CREATE OR REPLACE MACRO research_normalize_results(results_json, source_type) AS (
    SELECT CASE source_type
        WHEN 'arxiv' THEN jsonata(
            'results.{ "id": id, "title": title, "summary": summary, "published": published }',
            results_json
        )
        WHEN 'semantic_scholar' THEN jsonata(
            'data.{ "id": paperId, "title": title, "summary": abstract, "published": year }',
            results_json
        )
        WHEN 'searxng' THEN jsonata(
            'results.{ "id": url, "title": title, "summary": content, "source": engine }',
            results_json
        )
        ELSE results_json
    END
);

-- DevOrg: Validate JSON against schema-like rules
CREATE OR REPLACE MACRO dev_validate_config(config_json, required_fields) AS (
    SELECT json_object(
        'valid', jsonata('$count($keys($)) > 0', config_json)::BOOLEAN,
        'has_required', jsonata(
            '$join([' || required_fields || '], ",") in $keys($)',
            config_json
        ),
        'field_count', jsonata('$count($keys($))', config_json),
        'fields', jsonata('$keys($)', config_json)
    )
);

-- DevOrg: Transform package.json / pyproject.toml data
CREATE OR REPLACE MACRO dev_extract_deps(package_json) AS (
    SELECT jsonata(
        '{ "name": name, "version": version, "deps": $keys(dependencies), "devDeps": $keys(devDependencies) }',
        package_json
    )
);

-- =============================================================================
-- DUCKPGQ (OrchestratorOrg)
-- Property Graph Queries for agent relationships and task dependencies
-- =============================================================================

-- Create agent relationship graph
CREATE OR REPLACE MACRO create_agent_graph() AS (
    -- Vertex tables: orgs, agents, tasks
    -- Edge tables: org_calls (who calls whom), task_deps (task dependencies)
    SELECT 'CREATE PROPERTY GRAPH agent_network
        VERTEX TABLES (
            orgs PROPERTIES (id, name, org_type),
            agent_sessions PROPERTIES (id, agent_id, status)
        )
        EDGE TABLES (
            org_calls SOURCE KEY (caller_org) REFERENCES orgs (id)
                      DESTINATION KEY (target_org) REFERENCES orgs (id)
                      PROPERTIES (task, status)
        )'
);

-- OrchestratorOrg: Find shortest path between orgs
CREATE OR REPLACE MACRO orchestrator_find_path(from_org, to_org) AS (
    SELECT TRY(
        'FROM GRAPH_TABLE (agent_network
            MATCH (a:orgs WHERE a.id = ''' || from_org || ''')
                  -[e:org_calls]->*
                  (b:orgs WHERE b.id = ''' || to_org || ''')
            COLUMNS (a.id as source, b.id as target, path_length(e) as hops)
        )'
    )
);

-- OrchestratorOrg: Get org call chain
CREATE OR REPLACE MACRO orchestrator_call_chain(session_id_param) AS (
    SELECT json_group_array(json_object(
        'from', caller_org,
        'to', target_org,
        'task', task,
        'status', status
    ))
    FROM org_calls
    WHERE session_id = session_id_param
    ORDER BY created_at
);

-- Task dependency tracking
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id VARCHAR NOT NULL,
    depends_on VARCHAR NOT NULL,
    dependency_type VARCHAR DEFAULT 'blocks',
    PRIMARY KEY (task_id, depends_on)
);

-- OrchestratorOrg: Add task dependency
CREATE OR REPLACE MACRO orchestrator_add_dependency(task_id_param, depends_on_param, dep_type) AS (
    SELECT json_object(
        'action', 'orchestrator_add_dependency',
        'task_id', task_id_param,
        'depends_on', depends_on_param,
        'type', COALESCE(dep_type, 'blocks'),
        'status', 'pending_insert',
        'note', 'Dependency tracking handled by Python runtime'
    )
);

-- OrchestratorOrg: Get ready tasks (no unmet dependencies)
CREATE OR REPLACE MACRO orchestrator_get_ready_tasks() AS (
    SELECT t.id, t.task
    FROM org_calls t
    WHERE t.status = 'pending'
    AND NOT EXISTS (
        SELECT 1 FROM task_dependencies d
        JOIN org_calls blocker ON d.depends_on = blocker.id
        WHERE d.task_id = t.id AND blocker.status != 'completed'
    )
);

-- =============================================================================
-- BITFILTERS (OpsOrg + ResearchOrg)
-- Probabilistic data structures for deduplication and caching
-- =============================================================================

-- OpsOrg: Create log deduplication filter
CREATE TABLE IF NOT EXISTS ops_dedup_filters (
    filter_name VARCHAR PRIMARY KEY,
    filter_data BLOB,
    item_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now(),
    last_updated TIMESTAMP DEFAULT now()
);

-- OpsOrg: Check if log entry is duplicate (using hash + xor filter)
CREATE OR REPLACE MACRO ops_is_duplicate(filter_name_param, log_entry) AS (
    SELECT COALESCE(
        (SELECT xor8_filter_contains(filter_data, hash(log_entry)::UBIGINT)
         FROM ops_dedup_filters
         WHERE filter_name = filter_name_param),
        FALSE
    )
);

-- OpsOrg: Add entry to deduplication filter
CREATE OR REPLACE MACRO ops_add_to_filter(filter_name_param, entries_array) AS (
    -- Creates or updates XOR filter with new entries
    SELECT json_object(
        'filter', filter_name_param,
        'entries_added', len(entries_array),
        'note', 'Use xor8_create() to build filter from entries'
    )
);

-- ResearchOrg: Create citation fingerprint
CREATE OR REPLACE MACRO research_fingerprint(text_content) AS (
    -- Hash text for quick comparison
    SELECT hash(lower(regexp_replace(text_content, '\s+', ' ', 'g')))::UBIGINT
);

-- ResearchOrg: Batch duplicate detection
CREATE OR REPLACE MACRO research_find_duplicates(texts_table, text_column) AS (
    SELECT 'WITH fingerprints AS (
        SELECT *, research_fingerprint(' || text_column || ') as fp
        FROM ' || texts_table || '
    )
    SELECT a.*, b.* FROM fingerprints a
    JOIN fingerprints b ON a.fp = b.fp AND a.rowid < b.rowid'
);

-- =============================================================================
-- LINDEL (ResearchOrg + StudioOrg)
-- Space-filling curves for multi-dimensional data ordering
-- =============================================================================

-- ResearchOrg: Encode embedding for efficient storage/retrieval
CREATE OR REPLACE MACRO research_encode_embedding(embedding_array) AS (
    -- Hilbert encoding preserves locality better than Z-order
    SELECT hilbert_encode(embedding_array)
);

-- ResearchOrg: Decode back to embedding
CREATE OR REPLACE MACRO research_decode_embedding(hilbert_code, dimensions) AS (
    SELECT hilbert_decode(hilbert_code, dimensions, TRUE, FALSE)
);

-- StudioOrg: Organize assets by feature vectors
CREATE OR REPLACE MACRO studio_asset_order(feature_vector) AS (
    -- Morton/Z-order for asset clustering
    SELECT morton_encode(feature_vector)
);

-- StudioOrg: Create spatial index for assets
CREATE TABLE IF NOT EXISTS studio_asset_index (
    asset_id VARCHAR PRIMARY KEY,
    feature_vector DOUBLE[],
    hilbert_code UHUGEINT,
    morton_code UHUGEINT,
    created_at TIMESTAMP DEFAULT now()
);

-- StudioOrg: Index an asset
CREATE OR REPLACE MACRO studio_index_asset(asset_id_param, features) AS (
    SELECT json_object(
        'action', 'studio_index_asset',
        'asset_id', asset_id_param,
        'hilbert_code', hilbert_encode(features)::VARCHAR,
        'morton_code', morton_encode(features)::VARCHAR,
        'status', 'pending_insert',
        'note', 'Asset indexing handled by Python runtime'
    )
);

-- StudioOrg: Find similar assets (by Hilbert proximity)
CREATE OR REPLACE MACRO studio_find_similar(target_features, limit_count) AS (
    SELECT asset_id, feature_vector,
           abs(hilbert_code::BIGINT - hilbert_encode(target_features)::BIGINT) as distance
    FROM studio_asset_index
    ORDER BY distance
    LIMIT COALESCE(limit_count, 10)
);

-- =============================================================================
-- LSH (ResearchOrg)
-- Locality Sensitive Hashing for similarity search
-- =============================================================================

-- ResearchOrg: MinHash signature for text similarity
CREATE OR REPLACE MACRO research_minhash_signature(text_content, num_hashes) AS (
    -- Generate MinHash signature for Jaccard similarity
    SELECT lsh_min(text_content, COALESCE(num_hashes, 128))
);

-- ResearchOrg: Compare documents by MinHash
CREATE OR REPLACE MACRO research_jaccard_estimate(sig1, sig2) AS (
    -- Estimate Jaccard similarity from MinHash signatures
    SELECT lsh_jaccard(sig1, sig2)
);

-- Research document signatures table
CREATE TABLE IF NOT EXISTS research_doc_signatures (
    doc_id VARCHAR PRIMARY KEY,
    doc_title VARCHAR,
    minhash_sig UBIGINT[],
    created_at TIMESTAMP DEFAULT now()
);

-- ResearchOrg: Index document for similarity search
CREATE OR REPLACE MACRO research_index_doc(doc_id_param, doc_title_param, doc_content) AS (
    SELECT json_object(
        'action', 'research_index_doc',
        'doc_id', doc_id_param,
        'title', doc_title_param,
        'content_length', length(doc_content),
        'status', 'pending_insert',
        'note', 'Document indexing handled by Python runtime'
    )
);

-- ResearchOrg: Find similar documents
CREATE OR REPLACE MACRO research_find_similar_docs(query_content, threshold, limit_count) AS (
    WITH query_sig AS (
        SELECT research_minhash_signature(query_content, 128) as sig
    )
    SELECT doc_id, doc_title,
           research_jaccard_estimate(minhash_sig, query_sig.sig) as similarity
    FROM research_doc_signatures, query_sig
    WHERE research_jaccard_estimate(minhash_sig, query_sig.sig) >= COALESCE(threshold, 0.3)
    ORDER BY similarity DESC
    LIMIT COALESCE(limit_count, 10)
);

-- =============================================================================
-- RADIO (OrchestratorOrg + OpsOrg + StudioOrg)
-- Real-time event streams for agent coordination
-- =============================================================================

-- Radio subscriptions table
CREATE TABLE IF NOT EXISTS radio_subscriptions (
    sub_id VARCHAR PRIMARY KEY,
    org_id VARCHAR NOT NULL,
    channel_type VARCHAR NOT NULL, -- 'websocket', 'redis'
    channel_url VARCHAR NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

-- OrchestratorOrg: Subscribe to agent events
CREATE OR REPLACE MACRO orchestrator_subscribe(channel_url_param) AS (
    SELECT radio_subscribe(channel_url_param)
);

-- OrchestratorOrg: Broadcast task to agents
CREATE OR REPLACE MACRO orchestrator_broadcast(channel_param, message_json) AS (
    SELECT radio_transmit_message(channel_param, message_json)
);

-- OrchestratorOrg: Listen for agent responses (non-blocking)
CREATE OR REPLACE MACRO orchestrator_listen(timeout_ms) AS (
    SELECT radio_listen(COALESCE(timeout_ms, 1000))
);

-- OpsOrg: Subscribe to CI/CD events
CREATE OR REPLACE MACRO ops_subscribe_ci(ci_channel) AS (
    SELECT radio_subscribe(ci_channel)
);

-- OpsOrg: Publish deployment status
CREATE OR REPLACE MACRO ops_publish_status(channel_param, status_json) AS (
    SELECT radio_transmit_message(channel_param, json_object(
        'type', 'deployment_status',
        'timestamp', now()::VARCHAR,
        'data', status_json
    ))
);

-- StudioOrg: Real-time collaboration events
CREATE OR REPLACE MACRO studio_collab_event(project_id, event_type, event_data) AS (
    SELECT radio_transmit_message(
        'studio:' || project_id,
        json_object(
            'type', event_type,
            'project', project_id,
            'timestamp', now()::VARCHAR,
            'data', event_data
        )
    )
);

-- =============================================================================
-- SMART TOOL ROUTER
-- Automatic extension selection based on org and task
-- =============================================================================

-- Route to smart extension based on org and task type
CREATE OR REPLACE MACRO smart_route(org_id_param, task_type, task_params) AS (
    SELECT CASE
        -- ResearchOrg tasks
        WHEN org_id_param = 'research-org' AND task_type = 'parse_api'
            THEN research_parse_api(task_params)
        WHEN org_id_param = 'research-org' AND task_type = 'find_similar'
            THEN research_find_similar_docs(
                json_extract_string(task_params, '$.content'),
                json_extract(task_params, '$.threshold')::DOUBLE,
                json_extract(task_params, '$.limit')::INTEGER
            )
        WHEN org_id_param = 'research-org' AND task_type = 'encode_embedding'
            THEN research_encode_embedding(
                json_extract(task_params, '$.embedding')::DOUBLE[]
            )::VARCHAR

        -- OrchestratorOrg tasks
        WHEN org_id_param = 'orchestrator-org' AND task_type = 'broadcast'
            THEN orchestrator_broadcast(
                json_extract_string(task_params, '$.channel'),
                task_params
            )
        WHEN org_id_param = 'orchestrator-org' AND task_type = 'get_ready'
            THEN (SELECT json_group_array(json_object('id', id, 'task', task))
                  FROM orchestrator_get_ready_tasks())

        -- OpsOrg tasks
        WHEN org_id_param = 'ops-org' AND task_type = 'check_duplicate'
            THEN ops_is_duplicate(
                json_extract_string(task_params, '$.filter'),
                json_extract_string(task_params, '$.entry')
            )::VARCHAR
        WHEN org_id_param = 'ops-org' AND task_type = 'publish_status'
            THEN ops_publish_status(
                json_extract_string(task_params, '$.channel'),
                task_params
            )

        -- StudioOrg tasks
        WHEN org_id_param = 'studio-org' AND task_type = 'index_asset'
            THEN studio_index_asset(
                json_extract_string(task_params, '$.asset_id'),
                json_extract(task_params, '$.features')::DOUBLE[]
            )
        WHEN org_id_param = 'studio-org' AND task_type = 'find_similar'
            THEN (SELECT json_group_array(json_object(
                    'asset_id', asset_id,
                    'distance', distance
                  ))
                  FROM studio_find_similar(
                      json_extract(task_params, '$.features')::DOUBLE[],
                      json_extract(task_params, '$.limit')::INTEGER
                  ))
        WHEN org_id_param = 'studio-org' AND task_type = 'collab_event'
            THEN studio_collab_event(
                json_extract_string(task_params, '$.project'),
                json_extract_string(task_params, '$.event_type'),
                task_params
            )

        -- DevOrg tasks
        WHEN org_id_param = 'dev-org' AND task_type = 'validate_config'
            THEN dev_validate_config(
                task_params,
                json_extract_string(task_params, '$.required_fields')
            )
        WHEN org_id_param = 'dev-org' AND task_type = 'extract_deps'
            THEN dev_extract_deps(task_params)

        ELSE json_object('error', 'Unknown task type', 'org', org_id_param, 'task', task_type)
    END
);

-- =============================================================================
-- SYSTEM INTELLIGENCE SUMMARY
-- =============================================================================

-- Get system capabilities overview
CREATE OR REPLACE MACRO get_smart_capabilities() AS (
    SELECT json_object(
        'jsonata', json_object(
            'orgs', ['research-org', 'dev-org'],
            'capabilities', ['json_transform', 'api_parsing', 'config_validation']
        ),
        'duckpgq', json_object(
            'orgs', ['orchestrator-org'],
            'capabilities', ['agent_graph', 'task_dependencies', 'path_finding']
        ),
        'bitfilters', json_object(
            'orgs', ['ops-org', 'research-org'],
            'capabilities', ['deduplication', 'bloom_filters', 'cache_optimization']
        ),
        'lindel', json_object(
            'orgs', ['research-org', 'studio-org'],
            'capabilities', ['embedding_encoding', 'spatial_indexing', 'asset_clustering']
        ),
        'lsh', json_object(
            'orgs', ['research-org'],
            'capabilities', ['minhash', 'similarity_search', 'near_duplicate_detection']
        ),
        'radio', json_object(
            'orgs', ['orchestrator-org', 'ops-org', 'studio-org'],
            'capabilities', ['realtime_events', 'agent_coordination', 'pubsub']
        )
    )
);
