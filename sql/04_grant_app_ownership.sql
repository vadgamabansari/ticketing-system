-- Transfer table ownership to the app's runtime role.
--
-- Databricks Apps connects as ticketing-app-user (a native-password role,
-- see setup_secrets.py). If 01/02/03 were run interactively as a different
-- identity (e.g. your own OAuth user, needed because ticketing-app-user
-- can't authenticate through the browser SQL Editor's OAuth flow), that
-- identity ends up owning the tables. ensure_tables() in app.py then fails
-- on startup with "must be owner of table tickets" when it tries
-- CREATE INDEX IF NOT EXISTS on an existing table it doesn't own.
--
-- Run this once, as whichever role currently owns the tables (check with
-- the verification query below first if unsure).
--
-- Reassigning ownership requires being a MEMBER of the target role (able to
-- SET ROLE to it) - having databricks_superuser/CREATEROLE alone isn't
-- enough. Grant yourself membership first, do the reassignment, then
-- optionally revoke it again so you're not left as a standing member of
-- the app's role.

GRANT "ticketing-app-user" TO CURRENT_USER;

ALTER TABLE tickets OWNER TO "ticketing-app-user";
ALTER TABLE ticket_messages OWNER TO "ticketing-app-user";

-- Optional cleanup - uncomment to drop the membership you just granted:
-- REVOKE "ticketing-app-user" FROM CURRENT_USER;

-- Verify: both rows should show ticketing-app-user as the owner.
SELECT tablename, tableowner
FROM pg_tables
WHERE tablename IN ('tickets', 'ticket_messages');
