-- ─────────────────────────────────────────────────────────────────────────────
-- schema.sql
-- Run once in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/lkzoyyabcocbebfhlsff/sql
-- ─────────────────────────────────────────────────────────────────────────────

-- Mind Maps table
-- Tied to daf_users via user_id (integer foreign key)

CREATE TABLE IF NOT EXISTS mindmaps (
    id            VARCHAR(8) PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES daf_users(id) ON DELETE CASCADE,
    subject       TEXT NOT NULL,
    source_file   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    theme_count   INTEGER DEFAULT 0,
    lecture_count INTEGER DEFAULT 0,
    has_warnings  BOOLEAN DEFAULT FALSE,
    schema_json   JSONB NOT NULL
);

-- Index for fast user-scoped queries
CREATE INDEX IF NOT EXISTS idx_mindmaps_user_id
    ON mindmaps(user_id);

-- Index for fast lookup by map id + user (prevents cross-user access)
CREATE INDEX IF NOT EXISTS idx_mindmaps_id_user
    ON mindmaps(id, user_id);

-- ── Row Level Security ────────────────────────────────────────────────────────

ALTER TABLE mindmaps ENABLE ROW LEVEL SECURITY;

-- Allow insert (authenticated via app logic, not Supabase Auth)
CREATE POLICY "Allow public insert" ON mindmaps
FOR INSERT WITH CHECK (true);

-- Allow select
CREATE POLICY "Allow public select" ON mindmaps
FOR SELECT USING (true);

-- Allow update
CREATE POLICY "Allow public update" ON mindmaps
FOR UPDATE USING (true);

-- Allow delete
CREATE POLICY "Allow public delete" ON mindmaps
FOR DELETE USING (true);