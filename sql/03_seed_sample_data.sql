-- Sample data for tickets + ticket_messages.
-- Run after 01_create_tickets_table.sql and 02_create_ticket_messages_table.sql.
--
-- Idempotent: the whole block is a no-op if tickets already has rows, so
-- re-running this script (e.g. after a redeploy) never creates duplicates.
-- Satisfies the assignment minimums: 3 tickets, 3 distinct statuses,
-- 2+ messages per ticket.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tickets) THEN

        INSERT INTO tickets (title, status, priority, category, created_by) VALUES
            ('Login page throws 500 on submit', 'open', 'urgent', 'bug', 'alice@example.com'),
            ('Add dark mode to settings page', 'in_progress', 'medium', 'feature_request', 'bob@example.com'),
            ('Export to CSV missing timezone info', 'resolved', 'low', 'bug', 'carol@example.com');

        INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES
            ((SELECT ticket_id FROM tickets WHERE title = 'Login page throws 500 on submit'),
             'Can reproduce on both Chrome and Safari, stack trace attached in the internal doc.',
             'alice@example.com'),
            ((SELECT ticket_id FROM tickets WHERE title = 'Login page throws 500 on submit'),
             'Looks like a null pointer on the session token refresh path, investigating.',
             'dave@example.com'),

            ((SELECT ticket_id FROM tickets WHERE title = 'Add dark mode to settings page'),
             'Design mockups are ready, linking the Figma file in the next comment.',
             'bob@example.com'),
            ((SELECT ticket_id FROM tickets WHERE title = 'Add dark mode to settings page'),
             'Started on the CSS variable pass for the settings panel.',
             'erin@example.com'),

            ((SELECT ticket_id FROM tickets WHERE title = 'Export to CSV missing timezone info'),
             'Confirmed the exported timestamps are UTC but unlabeled, causing confusion downstream.',
             'carol@example.com'),
            ((SELECT ticket_id FROM tickets WHERE title = 'Export to CSV missing timezone info'),
             'Fixed by appending the offset to each timestamp column, verified against 3 sample exports.',
             'dave@example.com');

    END IF;
END $$;

-- Verify: expect 3 tickets and 6 messages after a fresh run.
SELECT
    (SELECT COUNT(*) FROM tickets) AS ticket_count,
    (SELECT COUNT(*) FROM ticket_messages) AS message_count,
    (SELECT COUNT(DISTINCT status) FROM tickets) AS distinct_statuses;
