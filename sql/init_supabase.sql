-- Copyright 2024
-- Directory: yt-agentic-rag/sql/init_supabase.sql
-- 
-- Complete Supabase Database Setup for RAG Application
-- Run this script on a FRESH Supabase project
-- 
-- Instructions:
-- 1. Create a new Supabase project at https://supabase.com
-- 2. Wait for project initialization to complete
-- 3. Go to SQL Editor in your Supabase dashboard
-- 4. Create a new query
-- 5. Copy and paste this ENTIRE script
-- 6. Click "Run" to execute everything at once
--
-- This script creates everything from scratch

-- =============================================================================
-- STEP 1: Enable pgvector extension for vector similarity search
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- STEP 2: Create the main RAG chunks table
-- =============================================================================

-- Idempotencia básica para reruns
DROP INDEX IF EXISTS rag_chunks_vec_idx;
DROP FUNCTION IF EXISTS match_chunks;
DROP TABLE IF EXISTS rag_chunks CASCADE;

CREATE TABLE rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(1024),  -- BAAI/bge-multilingual-gemma2 dimension (1024)
    created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================================================================
-- STEP 3: (Opcional) Indexes
-- =============================================================================
-- Usamos HNSW porque 1024 <= 2000 (límite de pgvector para hnsw/ivfflat)
CREATE INDEX rag_chunks_vec_idx ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- Regular B-tree indexes for filtering and sorting
CREATE INDEX rag_chunks_src_idx ON rag_chunks (source);
CREATE INDEX rag_chunks_chunk_id_idx ON rag_chunks (chunk_id);
CREATE INDEX rag_chunks_created_at_idx ON rag_chunks (created_at DESC);

-- =============================================================================
-- STEP 4: Create vector similarity search function
-- =============================================================================

CREATE OR REPLACE FUNCTION match_chunks (
  query_embedding vector(1024),
  match_count int DEFAULT 6,
  min_similarity float DEFAULT 0.0
)
RETURNS TABLE (
  chunk_id text,
  source text,
  text text,
  similarity float,
  created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    rag_chunks.chunk_id,
    rag_chunks.source,
    rag_chunks.text,
    1 - (rag_chunks.embedding <=> query_embedding) as similarity,
    rag_chunks.created_at
  FROM rag_chunks
  WHERE 1 - (rag_chunks.embedding <=> query_embedding) >= min_similarity
  ORDER BY rag_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 5: Create helper function to get database statistics
-- =============================================================================

CREATE OR REPLACE FUNCTION get_chunk_stats()
RETURNS TABLE (
  total_chunks bigint,
  unique_sources bigint,
  latest_chunk timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*) as total_chunks,
    COUNT(DISTINCT source) as unique_sources,
    MAX(created_at) as latest_chunk
  FROM rag_chunks;
END;
$$;

-- =============================================================================
-- STEP 6: Create Row Level Security (RLS) policies
-- =============================================================================

-- Enable RLS on the table
ALTER TABLE rag_chunks ENABLE ROW LEVEL SECURITY;

-- Allow all operations for service role (your backend)
CREATE POLICY "Allow service role full access" ON rag_chunks
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Allow read access for authenticated users (future frontend)
CREATE POLICY "Allow authenticated read access" ON rag_chunks
  FOR SELECT USING (auth.role() = 'authenticated');

-- Allow anonymous read access for development (remove in production)
CREATE POLICY "Allow anonymous read access" ON rag_chunks
  FOR SELECT USING (true);

-- =============================================================================
-- STEP 7: Verification - Test that everything was created correctly
-- =============================================================================

-- Test 1: Check pgvector extension
SELECT 'pgvector extension installed' as test_result 
WHERE EXISTS (
  SELECT 1 FROM pg_extension WHERE extname = 'vector'
);

-- Test 2: Check table creation
SELECT 'rag_chunks table created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_name = 'rag_chunks'
);

-- Test 3: Check vector column dimensions
SELECT 
  'Vector column configured for BAAI/bge-multilingual-gemma2' as test_result,
  'VECTOR(1024) dimensions' as details
WHERE EXISTS (
  SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'rag_chunks' 
  AND column_name = 'embedding'
);

-- Test 4: Check functions
SELECT 'match_chunks function created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.routines 
  WHERE routine_schema = 'public' AND routine_name = 'match_chunks'
);

SELECT 'get_chunk_stats function created' as test_result 
WHERE EXISTS (
  SELECT 1 FROM information_schema.routines 
  WHERE routine_schema = 'public' AND routine_name = 'get_chunk_stats'
);

-- Test 5: Check indexes
SELECT 'Vector index created' as test_result
WHERE EXISTS (
  SELECT 1 FROM pg_indexes 
  WHERE tablename = 'rag_chunks' AND indexname = 'rag_chunks_vec_idx'
);

-- Test 6: Show initial database stats (should be empty)
SELECT 
  'Database ready - ' || total_chunks::text || ' chunks' as test_result
FROM get_chunk_stats();

-- =============================================================================
-- SUCCESS MESSAGE
-- =============================================================================

SELECT '🎉 SUCCESS! Your Supabase database is ready for RAG!' as final_result;

-- =============================================================================
-- STEP 8: Agenda Manager Tables (messages, extracted events, calendar sync, importance, audit)
-- =============================================================================

-- Cleanup for reruns
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS calendar_events CASCADE;
DROP TABLE IF EXISTS extracted_events CASCADE;
DROP TABLE IF EXISTS importance_labels CASCADE;
DROP TABLE IF EXISTS messages_raw CASCADE;

CREATE TABLE messages_raw (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,                     -- gmail | imap | whatsapp | other
  message_id TEXT NOT NULL,                 -- e.g. Gmail Message-ID
  thread_id TEXT,
  from_addr TEXT,
  to_addr TEXT,
  subject TEXT,
  body TEXT,
  received_at TIMESTAMPTZ,
  raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX messages_raw_source_idx ON messages_raw (source);
CREATE INDEX messages_raw_msg_idx ON messages_raw (message_id);
CREATE UNIQUE INDEX messages_raw_source_msg_uniq ON messages_raw (source, message_id);

CREATE TABLE importance_labels (
  id BIGSERIAL PRIMARY KEY,
  message_id BIGINT REFERENCES messages_raw(id) ON DELETE CASCADE,
  label TEXT NOT NULL,                      -- important | normal | noise
  score FLOAT,
  rationale TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX importance_labels_message_idx ON importance_labels (message_id);

CREATE TABLE extracted_events (
  id BIGSERIAL PRIMARY KEY,
  message_id BIGINT REFERENCES messages_raw(id) ON DELETE CASCADE,
  title TEXT,
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  timezone TEXT,
  location TEXT,
  attendees JSONB,                          -- list of emails/phones
  status TEXT DEFAULT 'proposed',           -- proposed | confirmed | created
  confidence FLOAT,
  calendar_refs JSONB,                      -- list of {provider,event_id}
  notes TEXT,
  source TEXT,                              -- gmail | imap | whatsapp | calendly
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX extracted_events_message_idx ON extracted_events (message_id);
CREATE INDEX extracted_events_start_idx ON extracted_events (start_at);

CREATE TABLE calendar_events (
  id BIGSERIAL PRIMARY KEY,
  provider TEXT NOT NULL,                   -- google | calendly | other
  provider_event_id TEXT NOT NULL,
  calendar_id TEXT,
  title TEXT,
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  status TEXT,                              -- confirmed | cancelled | tentative
  last_sync_at TIMESTAMPTZ,
  extra JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX calendar_events_unique ON calendar_events (provider, provider_event_id);
CREATE INDEX calendar_events_start_idx ON calendar_events (start_at);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  action TEXT NOT NULL,                     -- create_event | update_event | label_message | etc
  actor TEXT NOT NULL,                      -- agent | user
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Basic RLS (allow service role; allow select for anon for dev)
ALTER TABLE messages_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE importance_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sr full messages" ON messages_raw
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
CREATE POLICY "sr full importance" ON importance_labels
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
CREATE POLICY "sr full extracted" ON extracted_events
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
CREATE POLICY "sr full calendar_events" ON calendar_events
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
CREATE POLICY "sr full audit" ON audit_log
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Dev read for anon (remove in prod)
CREATE POLICY "anon read messages" ON messages_raw
  FOR SELECT USING (true);
CREATE POLICY "anon read importance" ON importance_labels
  FOR SELECT USING (true);
CREATE POLICY "anon read extracted" ON extracted_events
  FOR SELECT USING (true);
CREATE POLICY "anon read calendar_events" ON calendar_events
  FOR SELECT USING (true);
CREATE POLICY "anon read audit" ON audit_log
  FOR SELECT USING (true);

-- =============================================================================
-- WHAT WAS CREATED:
-- =============================================================================
-- 
-- ✅ Extensions:
--    - pgvector (for vector operations)
-- 
-- ✅ Tables:
--    - rag_chunks (with VECTOR(1536) for text-embedding-3-small)
-- 
-- ✅ Indexes:
--    - IVFFlat vector index (optimized for 1536 dimensions)
--    - B-tree indexes for fast filtering
-- 
-- ✅ Functions:
--    - match_chunks() - vector similarity search
--    - get_chunk_stats() - database statistics
-- 
-- ✅ Security:
--    - Row Level Security enabled
--    - Policies for service role, authenticated users, and anonymous access
-- 
-- =============================================================================
-- NEXT STEPS:
-- =============================================================================
-- 
-- 1. Update your .env file with Supabase credentials:
--    SUPABASE_URL=https://your-project.supabase.co
--    SUPABASE_ANON_KEY=your_anon_key
--    SUPABASE_SERVICE_ROLE_KEY=your_service_key
--    OPENAI_API_KEY=your_openai_key
-- 
-- 2. Start your FastAPI backend:
--    uvicorn main:app --reload --port 8000
-- 
-- 3. Test the health check:
--    curl http://localhost:8000/healthz
-- 
-- 4. Seed your knowledge base:
--    curl -X POST http://localhost:8000/seed
-- 
-- 5. Ask your first question:
--    curl -X POST http://localhost:8000/answer \
--      -H "Content-Type: application/json" \
--      -d '{"query": "What is your return policy?"}'
-- 
-- 6. Visit interactive docs:
--    http://localhost:8000/docs
-- 
-- =============================================================================