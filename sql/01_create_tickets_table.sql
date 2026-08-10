-- Setup script for the tickets table.
-- Run this manually against your Lakebase Postgres instance (SQL editor or
-- psql using LAKEBASE_URL) before starting the app. Safe to re-run.
--
-- Soft delete: deleted_at is set instead of removing the row, so the
-- "delete with confirmation" bonus feature is reversible and message
-- history under a deleted ticket isn't destroyed. All app queries against
-- this table should filter WHERE deleted_at IS NULL unless explicitly
-- showing deleted tickets.

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'resolved')),
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    category    TEXT NOT NULL DEFAULT 'other'
                CHECK (category IN ('bug', 'feature_request', 'question', 'other')),
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

-- Filtering by status (bonus feature) and excluding soft-deleted rows are
-- the two most common WHERE clauses this table will see.
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status);
CREATE INDEX IF NOT EXISTS idx_tickets_deleted_at ON tickets (deleted_at);

-- Verify the table was created as expected.
SELECT
    table_name,
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tickets'
ORDER BY ordinal_position;
