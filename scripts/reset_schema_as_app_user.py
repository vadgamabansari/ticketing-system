"""
One-off local utility: connect directly as ticketing-app-user (bypassing
the Databricks browser SQL Editor, which appears to always execute as your
own OAuth identity regardless of the Role dropdown) and (re)create the
schema so tickets/ticket_messages are owned by ticketing-app-user from the
start. Avoids the "must be owner of table tickets" crash ensure_tables()
hits in app.py when the app's runtime role doesn't own objects created
under a different identity - and avoids needing GRANT/ALTER OWNER
privileges that a managed-Postgres role like databricks_superuser doesn't
actually have.

This DROPS and recreates tickets/ticket_messages, so any existing rows
are lost - sql/03_seed_sample_data.sql is re-run at the end to reseed.

Usage:
    pip install psycopg2-binary
    python scripts/reset_schema_as_app_user.py
    # paste the ticketing-app-user connection URL when prompted
    # (Lakebase project -> Connect -> Role: ticketing-app-user -> Show password)
"""

import getpass
from pathlib import Path

import psycopg2

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SQL_FILES = (
    "01_create_tickets_table.sql",
    "02_create_ticket_messages_table.sql",
    "03_seed_sample_data.sql",
)

conn_url = getpass.getpass("Paste the ticketing-app-user Lakebase connection URL: ")

conn = psycopg2.connect(conn_url)
conn.autocommit = True

with conn.cursor() as cur:
    print("Dropping existing tables (if any)...")
    cur.execute("DROP TABLE IF EXISTS ticket_messages")
    cur.execute("DROP TABLE IF EXISTS tickets")

    for filename in SQL_FILES:
        print(f"Running {filename}...")
        cur.execute((SQL_DIR / filename).read_text())

    cur.execute(
        "SELECT tablename, tableowner FROM pg_tables "
        "WHERE tablename IN ('tickets', 'ticket_messages')"
    )
    for row in cur.fetchall():
        print(row)

conn.close()
print("Done - both tables should now show ticketing-app-user as owner.")
