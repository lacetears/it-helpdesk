"""Local single-operator help desk. Not an internet-facing multi-user service."""

import os, secrets, sqlite3
from pathlib import Path
from flask import Flask, abort, g, redirect, render_template, request, session, url_for

STATUSES = ("Open", "In progress", "Resolved")
PRIORITIES = ("Low", "Medium", "High", "Critical")


def create_app(config=None):
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parent))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(Path(__file__).with_name("tickets.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=32768,
    )
    if config:
        app.config.update(config)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close(error=None):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    with app.app_context():
        db().executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
          requester TEXT NOT NULL, assignee TEXT NOT NULL DEFAULT '',
          priority TEXT NOT NULL CHECK(priority IN ('Low','Medium','High','Critical')),
          status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open','In progress','Resolved')),
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS history (
          id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, detail TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)

    @app.before_request
    def csrf():
        session.setdefault("csrf", secrets.token_hex(32))
        if request.method == "POST" and not secrets.compare_digest(
            session["csrf"], request.form.get("csrf", "")
        ):
            abort(400, "Invalid CSRF token. Reload the page.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.get("/")
    def index():
        q = request.args.get("q", "").strip()[:200]
        status = request.args.get("status", "")
        sql = "SELECT * FROM tickets WHERE (title LIKE ? OR description LIKE ? OR requester LIKE ?)"
        args = [f"%{q}%"] * 3
        if status in STATUSES:
            sql += " AND status=?"
            args.append(status)
        rows = db().execute(sql + " ORDER BY id DESC", args).fetchall()
        counts = {
            r["status"]: r["n"]
            for r in db().execute(
                "SELECT status,COUNT(*) n FROM tickets GROUP BY status"
            )
        }
        return render_template(
            "index.html",
            tickets=rows,
            counts=counts,
            q=q,
            status=status,
            statuses=STATUSES,
            priorities=PRIORITIES,
        )

    @app.post("/tickets")
    def create():
        values = {
            k: request.form.get(k, "").strip()
            for k in ("title", "description", "requester", "priority")
        }
        if not all(values.values()) or values["priority"] not in PRIORITIES:
            abort(400, "Complete all fields with a valid priority.")
        if (
            len(values["title"]) > 120
            or len(values["requester"]) > 120
            or len(values["description"]) > 5000
        ):
            abort(400, "Field too long.")
        c = db().execute(
            "INSERT INTO tickets(title,description,requester,priority) VALUES (?,?,?,?)",
            tuple(values.values()),
        )
        db().execute(
            "INSERT INTO history(ticket_id,detail) VALUES (?,?)",
            (c.lastrowid, "Ticket created"),
        )
        db().commit()
        return redirect(url_for("detail", ticket_id=c.lastrowid))

    @app.post("/tickets/<int:ticket_id>/notes")
    def add_note(ticket_id):
        if (
            db().execute("SELECT id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            is None
        ):
            abort(404)
        note = request.form.get("note", "").strip()
        if not note or len(note) > 2000:
            abort(400, "A note must contain between 1 and 2,000 characters.")
        db().execute(
            "INSERT INTO history(ticket_id,detail) VALUES (?,?)",
            (ticket_id, "Note: " + note),
        )
        db().execute(
            "UPDATE tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (ticket_id,)
        )
        db().commit()
        return redirect(url_for("detail", ticket_id=ticket_id))

    @app.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
    def detail(ticket_id):
        ticket = (
            db().execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        )
        if ticket is None:
            abort(404)
        if request.method == "POST":
            status = request.form.get("status")
            priority = request.form.get("priority")
            assignee = request.form.get("assignee", "").strip()
            if (
                status not in STATUSES
                or priority not in PRIORITIES
                or len(assignee) > 120
            ):
                abort(400, "Invalid update.")
            db().execute(
                "UPDATE tickets SET status=?,priority=?,assignee=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, priority, assignee, ticket_id),
            )
            detail = f"Status: {ticket['status']} → {status}; priority: {ticket['priority']} → {priority}; assignee: {ticket['assignee']} → {assignee}"
            db().execute(
                "INSERT INTO history(ticket_id,detail) VALUES (?,?)",
                (ticket_id, detail),
            )
            db().commit()
            return redirect(url_for("detail", ticket_id=ticket_id))
        history = (
            db()
            .execute(
                "SELECT * FROM history WHERE ticket_id=? ORDER BY id DESC", (ticket_id,)
            )
            .fetchall()
        )
        return render_template(
            "detail.html",
            ticket=ticket,
            history=history,
            statuses=STATUSES,
            priorities=PRIORITIES,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
