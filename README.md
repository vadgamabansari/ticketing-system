# Ticketing System — Lakebase-Powered Databricks App

A small internal support-ticket app: users create tickets, add messages to
them, and update ticket status. All operational data lives in **Lakebase**
(Databricks-managed Postgres) — nothing is hard-coded.

Built on the connection/deploy pattern from `databricks-lakebase-app-day-1`
in this repo's parent folder: Flask + Lakebase via a single secret-scoped
connection string, deployed as a Databricks App from a Git folder (no CLI
required).

## Repo structure

```
ticketing-system/
├── sql/                          # versioned schema, run once against Lakebase
│   ├── 01_create_tickets_table.sql
│   ├── 02_create_ticket_messages_table.sql
│   └── 03_seed_sample_data.sql
└── src/                          # the Databricks App itself
    ├── app.py                     # Flask routes
    ├── lakebase.py                 # Lakebase connection helper
    ├── setup_secrets.py             # one-time secret scope setup
    ├── app.yaml                     # Databricks App config
    ├── requirements.txt
    ├── .env.example
    ├── templates/index.html
    └── static/{style.css,app.js}
```

## Schema

**tickets**: `ticket_id, title, status, priority, category, created_by, created_at, deleted_at`
**ticket_messages**: `message_id, ticket_id (FK -> tickets), message_text, author, created_at`

`status` ∈ `open | in_progress | resolved`, `priority` ∈ `low | medium | high | urgent`,
`category` ∈ `bug | feature_request | question | other`. Deletes are **soft**
(`deleted_at` set, row kept) so the delete-confirmation bonus feature is
reversible and doesn't destroy a ticket's message history.

## 1. Create a Lakebase instance + native-password role

1. Databricks workspace → **Catalog** → **Lakebase** tab → **Create Lakebase instance**.
2. Once **Available**, open it → **Roles & Databases** → enable **native (password) authentication**
   if not already on (Lakebase defaults to OAuth/short-lived tokens).
3. **Add role** → choose **Password** auth → name it (e.g. `ticketing_app`).
4. Copy the connection URL shown:
   `postgresql://<role>:<password>@<host>.database.cloud.databricks.com:5432/databricks_postgres?sslmode=require`

## 2. Store the connection URL as a secret

From a Databricks notebook (`%sh python setup_secrets.py`) or locally with
`databricks auth login` configured:

```bash
cd src
python setup_secrets.py
```

Paste the connection URL from step 1 when prompted. This stores it as secret
`database/ticketing-lakebase-url` — a dedicated key so it doesn't collide
with the plain `lakebase-url` key this workspace's other bootcamp apps use
in the same `database` scope. `app.yaml` and `lakebase.py` only ever
reference the scope/key names, never the value itself.

## 3. Create the schema + seed data

Run `sql/01_create_tickets_table.sql`, then `sql/02_create_ticket_messages_table.sql`,
then `sql/03_seed_sample_data.sql` against the Lakebase instance (Databricks SQL editor,
connected to the instance, or `psql` using the connection URL). All three are
safe to re-run. `app.py` also calls `ensure_tables()` on startup as a
belt-and-suspenders fallback for a fresh instance.

`ticketing-app-user` (the app's runtime role) can't authenticate through the
browser SQL Editor's OAuth flow, so `01`–`03` typically get run as your own
OAuth user instead — which leaves that user owning the tables. Since
`ensure_tables()` runs `CREATE INDEX IF NOT EXISTS` on every app startup,
and that requires table ownership, also run **`sql/04_grant_app_ownership.sql`**
once (as the user who owns the tables) to transfer ownership to
`ticketing-app-user` — otherwise the app crashes on boot with
`InsufficientPrivilege: must be owner of table tickets`.

## 4. Run locally

```bash
cd src
cp .env.example .env
pip install -r requirements.txt
python app.py
```

Requires `databricks auth login` to be configured locally — `lakebase.py`
fetches the secret via the Databricks SDK on every connection, there's no
separate local-only credential path. Open `http://localhost:8000`.

## 5. Deploy

1. Workspace → **Create** → **Git folder** → paste this repo's Git URL.
2. Compute → **Apps** → **Create app** → **Custom**, point the source at the
   Git folder's **`ticketing-system/src/`** subfolder (must contain `app.yaml`).
3. **Deploy**. To update later: pull in the Git folder, click **Deploy** again.

## 6. Verify

- [ ] Existing (seeded) tickets load on the deployed URL
- [ ] A new ticket can be created
- [ ] A message can be added to a ticket
- [ ] A ticket's status can be updated
- [ ] Filtering by status works
- [ ] Stats strip reflects current counts
- [ ] Delete asks for confirmation, then removes the ticket from the list
- [ ] Refreshing the page preserves all of the above

## API

| Method & path | Purpose |
|---|---|
| `GET /tickets?status=&priority=&category=` | list, filterable |
| `GET /tickets/<id>` | ticket + its messages |
| `POST /tickets` | create |
| `PATCH /tickets/<id>/status` | update status |
| `DELETE /tickets/<id>` | soft delete |
| `GET/POST /tickets/<id>/messages` | list / add messages |
| `GET /stats` | counts by status/priority + totals |

## Bonus features implemented

Priority/category, status filtering, server-side input validation with
inline error messages, a stats strip, soft delete with a confirmation
modal, and a custom (non-framework) visual design with status/priority
badges and light/dark support.

## Note on the free tier

Lakebase's **Change Data Feed** is not available on Databricks free/Community
Edition — not needed for this assignment, just worth knowing if you extend
this project later.
