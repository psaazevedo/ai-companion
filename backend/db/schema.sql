CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_input TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    summary TEXT NOT NULL,
    emotional_tone TEXT NOT NULL,
    salience DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    memory_status TEXT NOT NULL DEFAULT 'active',
    recall_count INTEGER NOT NULL DEFAULT 0,
    stability DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    archive_reason TEXT,
    archived_at TIMESTAMPTZ,
    input_mode TEXT NOT NULL DEFAULT 'voice',
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    restricted_reason TEXT,
    dialogue_signals JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(__EMBEDDING_DIMENSIONS__),
    search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(user_input, '') || ' ' || coalesce(summary, ''))
    ) STORED
);

CREATE TABLE IF NOT EXISTS dialogue_profiles (
    user_id TEXT PRIMARY KEY,
    sample_count INTEGER NOT NULL DEFAULT 0,
    avg_words_per_turn DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    hedging_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    indirectness_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ramble_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    disfluency_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    filler_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    self_correction_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    pause_tolerance_seconds DOUBLE PRECISION NOT NULL DEFAULT 0.9,
    last_observed_episode_id UUID,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS semantic_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    fact_key TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.7,
    reinforcement_count INTEGER NOT NULL DEFAULT 1,
    private_reinforcement_count INTEGER NOT NULL DEFAULT 0,
    recall_count INTEGER NOT NULL DEFAULT 0,
    memory_status TEXT NOT NULL DEFAULT 'active',
    archive_reason TEXT,
    archived_at TIMESTAMPTZ,
    source_episode_ids TEXT[] NOT NULL DEFAULT '{}',
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    restricted_reason TEXT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    superseded_by UUID,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding VECTOR(__EMBEDDING_DIMENSIONS__),
    search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(content, ''))
    ) STORED
);

CREATE TABLE IF NOT EXISTS procedural_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    pattern_key TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.7,
    reinforcement_count INTEGER NOT NULL DEFAULT 1,
    private_reinforcement_count INTEGER NOT NULL DEFAULT 0,
    recall_count INTEGER NOT NULL DEFAULT 0,
    memory_status TEXT NOT NULL DEFAULT 'active',
    archive_reason TEXT,
    archived_at TIMESTAMPTZ,
    source_episode_ids TEXT[] NOT NULL DEFAULT '{}',
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    restricted_reason TEXT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    superseded_by UUID,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding VECTOR(__EMBEDDING_DIMENSIONS__),
    search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(content, ''))
    ) STORED
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    label TEXT NOT NULL,
    node_type TEXT NOT NULL DEFAULT 'concept',
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    restricted_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, label)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    source_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 0.4,
    recall_count INTEGER NOT NULL DEFAULT 0,
    source_episode_ids TEXT[] NOT NULL DEFAULT '{}',
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    restricted_reason TEXT,
    edge_status TEXT NOT NULL DEFAULT 'active',
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, source_node_id, target_node_id, relation)
);

CREATE TABLE IF NOT EXISTS proactive_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    insight_key TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    source_memory_ids TEXT[] NOT NULL DEFAULT '{}',
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS background_job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    status TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS memory_mutations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    memory_layer TEXT NOT NULL,
    memory_id UUID,
    action TEXT NOT NULL,
    reason TEXT,
    source_episode_id TEXT,
    from_status TEXT,
    to_status TEXT,
    conversation_mode TEXT NOT NULL DEFAULT 'general',
    visibility_scope TEXT NOT NULL DEFAULT 'global',
    allowed_modes TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Compatibility migrations must run before indexes because older databases
-- may not have newer columns yet.
ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS dialogue_signals JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS input_mode TEXT NOT NULL DEFAULT 'voice';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS fact_key TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS private_reinforcement_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS archive_reason TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS pattern_key TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS private_reinforcement_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS archive_reason TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS source_episode_ids TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS edge_status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_episodes_user_time
    ON episodes(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_user_status
    ON episodes(user_id, memory_status);

CREATE INDEX IF NOT EXISTS idx_episodes_user_scope
    ON episodes(user_id, visibility_scope, conversation_mode);

CREATE INDEX IF NOT EXISTS idx_semantic_user_status
    ON semantic_memories(user_id, memory_status);

CREATE INDEX IF NOT EXISTS idx_semantic_user_scope
    ON semantic_memories(user_id, visibility_scope, conversation_mode);

CREATE INDEX IF NOT EXISTS idx_procedural_user_status
    ON procedural_memories(user_id, memory_status);

CREATE INDEX IF NOT EXISTS idx_procedural_user_scope
    ON procedural_memories(user_id, visibility_scope, conversation_mode);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_user_label
    ON graph_nodes(user_id, label);

CREATE INDEX IF NOT EXISTS idx_graph_edges_user_weight
    ON graph_edges(user_id, weight DESC);

CREATE INDEX IF NOT EXISTS idx_proactive_insights_user_status
    ON proactive_insights(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_background_job_runs_job_name
    ON background_job_runs(job_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_mutations_user_created
    ON memory_mutations(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_mutations_memory
    ON memory_mutations(memory_layer, memory_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_search_tsv
    ON episodes USING GIN(search_tsv);

CREATE INDEX IF NOT EXISTS idx_semantic_search_tsv
    ON semantic_memories USING GIN(search_tsv);

CREATE INDEX IF NOT EXISTS idx_procedural_search_tsv
    ON procedural_memories USING GIN(search_tsv);

CREATE INDEX IF NOT EXISTS idx_episodes_embedding_hnsw
    ON episodes USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_semantic_embedding_hnsw
    ON semantic_memories USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_procedural_embedding_hnsw
    ON procedural_memories USING hnsw (embedding vector_cosine_ops);

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS dialogue_signals JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS input_mode TEXT NOT NULL DEFAULT 'voice';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE episodes
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS fact_key TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS private_reinforcement_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS archive_reason TEXT;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE semantic_memories
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS pattern_key TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS private_reinforcement_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS archive_reason TEXT;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS superseded_by UUID;

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE procedural_memories
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_nodes
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS source_episode_ids TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS edge_status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS conversation_mode TEXT NOT NULL DEFAULT 'general';

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS visibility_scope TEXT NOT NULL DEFAULT 'global';

ALTER TABLE proactive_insights
    ADD COLUMN IF NOT EXISTS allowed_modes TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_semantic_user_fact_key
    ON semantic_memories(user_id, fact_key);

CREATE INDEX IF NOT EXISTS idx_procedural_user_pattern_key
    ON procedural_memories(user_id, pattern_key);

CREATE INDEX IF NOT EXISTS idx_semantic_user_validity
    ON semantic_memories(user_id, valid_to, last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_procedural_user_validity
    ON procedural_memories(user_id, valid_to, last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_graph_edges_user_status
    ON graph_edges(user_id, edge_status, last_seen DESC);

CREATE INDEX IF NOT EXISTS idx_graph_edges_user_scope
    ON graph_edges(user_id, visibility_scope, conversation_mode);

CREATE INDEX IF NOT EXISTS idx_dialogue_profiles_last_updated
    ON dialogue_profiles(last_updated DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_proactive_insights_pending_key
    ON proactive_insights(user_id, insight_key)
    WHERE status = 'pending';
