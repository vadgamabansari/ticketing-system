"""
Ticketing System - Databricks App.

Flask app backed by Lakebase (Databricks-managed Postgres). Reads/writes
tickets and ticket_messages via lakebase.py - no hard-coded application data.

Run locally:
    python app.py
Deploy as a Databricks App using app.yaml.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()  # must run before `import lakebase` - it reads secret scope/key env vars at import time

from databricks.sdk import WorkspaceClient
from flask import Flask, abort, jsonify, render_template, request

import lakebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketing-app")

app = Flask(__name__)
_w = WorkspaceClient()

ALLOWED_STATUSES = {"open", "in_progress", "resolved"}
ALLOWED_PRIORITIES = {"low", "medium", "high", "urgent"}
ALLOWED_CATEGORIES = {"bug", "feature_request", "question", "other"}
MAX_TITLE_LENGTH = 200
MAX_MESSAGE_LENGTH = 2000

TICKET_COLUMNS = "ticket_id, title, status, priority, category, created_by, created_at"


def ensure_tables():
    """Create tickets/ticket_messages if they don't exist yet (mirrors sql/01, sql/02)."""
    lakebase.run_write(
        """
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
        )
        """
    )
    lakebase.run_write(
        "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status)"
    )
    lakebase.run_write(
        "CREATE INDEX IF NOT EXISTS idx_tickets_deleted_at ON tickets (deleted_at)"
    )
    lakebase.run_write(
        """
        CREATE TABLE IF NOT EXISTS ticket_messages (
            message_id    SERIAL PRIMARY KEY,
            ticket_id     INTEGER NOT NULL REFERENCES tickets (ticket_id) ON DELETE RESTRICT,
            message_text  TEXT NOT NULL,
            author        TEXT NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    lakebase.run_write(
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages (ticket_id)"
    )


def _current_user_email() -> str:
    """
    Resolve the current user's email so created_by/author can be set from
    the real logged-in user instead of a free-text field.

    Databricks Apps inject the logged-in user's identity via the
    X-Forwarded-Email header on every request. Fall back to the Databricks
    SDK's current_user API for local development where that header isn't set.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


def _validate_ticket_payload(data: dict) -> str | None:
    """Return an error message if the create-ticket payload is invalid, else None."""
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return "title is required"
    if len(title.strip()) > MAX_TITLE_LENGTH:
        return f"title must be {MAX_TITLE_LENGTH} characters or fewer"

    status = data.get("status", "open")
    if status not in ALLOWED_STATUSES:
        return f"status must be one of {sorted(ALLOWED_STATUSES)}"

    priority = data.get("priority", "medium")
    if priority not in ALLOWED_PRIORITIES:
        return f"priority must be one of {sorted(ALLOWED_PRIORITIES)}"

    category = data.get("category", "other")
    if category not in ALLOWED_CATEGORIES:
        return f"category must be one of {sorted(ALLOWED_CATEGORIES)}"

    return None


def _validate_message_payload(data: dict) -> str | None:
    """Return an error message if the add-message payload is invalid, else None."""
    message_text = data.get("message_text", "")
    if not isinstance(message_text, str) or not message_text.strip():
        return "message_text is required"
    if len(message_text.strip()) > MAX_MESSAGE_LENGTH:
        return f"message_text must be {MAX_MESSAGE_LENGTH} characters or fewer"
    return None


def _get_ticket_or_404(ticket_id: int) -> dict:
    rows = lakebase.run_query(
        f"SELECT {TICKET_COLUMNS} FROM tickets WHERE ticket_id = %s AND deleted_at IS NULL",
        (ticket_id,),
    )
    if not rows:
        abort(404, description=f"Ticket {ticket_id} not found")
    return rows[0]


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure all unhandled errors return JSON (not an HTML error page),
    so the frontend's fetch().json() calls never choke on HTML."""
    logger.exception("Unhandled exception while processing request")
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/tickets")
def list_tickets():
    """List tickets, optionally filtered by status/priority/category query params."""
    conditions = ["deleted_at IS NULL"]
    params: list[str] = []

    for field in ("status", "priority", "category"):
        value = request.args.get(field)
        if value:
            conditions.append(f"{field} = %s")
            params.append(value)

    where_clause = " AND ".join(conditions)
    rows = lakebase.run_query(
        f"SELECT {TICKET_COLUMNS} FROM tickets WHERE {where_clause} ORDER BY created_at DESC",
        tuple(params),
    )
    return jsonify(rows)


@app.route("/tickets/<int:ticket_id>")
def get_ticket(ticket_id):
    """Single ticket plus its messages, in one payload."""
    ticket = _get_ticket_or_404(ticket_id)
    messages = lakebase.run_query(
        "SELECT message_id, ticket_id, message_text, author, created_at "
        "FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,),
    )
    return jsonify({"ticket": ticket, "messages": messages})


@app.route("/tickets", methods=["POST"])
def create_ticket():
    data = request.get_json(silent=True) or {}
    error = _validate_ticket_payload(data)
    if error:
        return jsonify({"error": error}), 400

    rows = lakebase.run_write_returning(
        f"""
        INSERT INTO tickets (title, status, priority, category, created_by)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING {TICKET_COLUMNS}
        """,
        (
            data["title"].strip(),
            data.get("status", "open"),
            data.get("priority", "medium"),
            data.get("category", "other"),
            _current_user_email(),
        ),
    )
    return jsonify(rows[0]), 201


@app.route("/tickets/<int:ticket_id>/status", methods=["PATCH"])
def update_ticket_status(ticket_id):
    _get_ticket_or_404(ticket_id)
    data = request.get_json(silent=True) or {}
    status = data.get("status", "")
    if status not in ALLOWED_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"}), 400

    rows = lakebase.run_write_returning(
        f"""
        UPDATE tickets SET status = %s
        WHERE ticket_id = %s AND deleted_at IS NULL
        RETURNING {TICKET_COLUMNS}
        """,
        (status, ticket_id),
    )
    return jsonify(rows[0])


@app.route("/tickets/<int:ticket_id>", methods=["DELETE"])
def delete_ticket(ticket_id):
    """Soft delete - sets deleted_at rather than removing the row. The
    confirmation step lives in the UI; this endpoint deletes unconditionally
    once called."""
    _get_ticket_or_404(ticket_id)
    lakebase.run_write(
        "UPDATE tickets SET deleted_at = now() WHERE ticket_id = %s",
        (ticket_id,),
    )
    return jsonify({"deleted": ticket_id})


@app.route("/tickets/<int:ticket_id>/messages")
def list_messages(ticket_id):
    _get_ticket_or_404(ticket_id)
    rows = lakebase.run_query(
        "SELECT message_id, ticket_id, message_text, author, created_at "
        "FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,),
    )
    return jsonify(rows)


@app.route("/tickets/<int:ticket_id>/messages", methods=["POST"])
def add_message(ticket_id):
    _get_ticket_or_404(ticket_id)
    data = request.get_json(silent=True) or {}
    error = _validate_message_payload(data)
    if error:
        return jsonify({"error": error}), 400

    rows = lakebase.run_write_returning(
        """
        INSERT INTO ticket_messages (ticket_id, message_text, author)
        VALUES (%s, %s, %s)
        RETURNING message_id, ticket_id, message_text, author, created_at
        """,
        (ticket_id, data["message_text"].strip(), _current_user_email()),
    )
    return jsonify(rows[0]), 201


@app.route("/stats")
def stats():
    by_status = lakebase.run_query(
        "SELECT status, COUNT(*) AS count FROM tickets WHERE deleted_at IS NULL GROUP BY status"
    )
    by_priority = lakebase.run_query(
        "SELECT priority, COUNT(*) AS count FROM tickets WHERE deleted_at IS NULL GROUP BY priority"
    )
    totals = lakebase.run_query(
        """
        SELECT
            (SELECT COUNT(*) FROM tickets WHERE deleted_at IS NULL) AS total_tickets,
            (SELECT COUNT(*) FROM ticket_messages m
                JOIN tickets t ON t.ticket_id = m.ticket_id
                WHERE t.deleted_at IS NULL) AS total_messages
        """
    )
    return jsonify({"by_status": by_status, "by_priority": by_priority, **totals[0]})


ensure_tables()

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", 8000))
    app.run(debug=True, host=host, port=port)
