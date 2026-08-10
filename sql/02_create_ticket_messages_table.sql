-- Setup script for the ticket_messages table.
-- Run this manually against your Lakebase Postgres instance, after
-- 01_create_tickets_table.sql. Safe to re-run.
--
-- ticket_id references tickets(ticket_id) per the assignment requirement.
-- No ON DELETE CASCADE: tickets are soft-deleted (see 01_...sql), so a
-- hard cascade here is never triggered by normal app behavior; RESTRICT
-- is the safer default in case a ticket row is ever hard-deleted by hand.

CREATE TABLE IF NOT EXISTS ticket_messages (
    message_id    SERIAL PRIMARY KEY,
    ticket_id     INTEGER NOT NULL REFERENCES tickets (ticket_id) ON DELETE RESTRICT,
    message_text  TEXT NOT NULL,
    author        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every read of a ticket's messages filters/joins on ticket_id.
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages (ticket_id);

-- Verify the table was created as expected.
SELECT
    table_name,
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticket_messages'
ORDER BY ordinal_position;
