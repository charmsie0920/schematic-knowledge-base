-- docker/postgres/init/01-extensions.sql

-- pgvector: vector column type + ANN indexes (HNSW / IVFFlat).
-- This is what lets one database serve both vector and keyword search.
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_trgm: trigram similarity, used for fuzzy matching and to
-- accelerate ILIKE lookups alongside full-text search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sanity output, visible in `docker compose logs postgres` on first boot.
DO $$
BEGIN
  RAISE NOTICE 'Recall: extensions vector + pg_trgm enabled.';
END $$;
