"""Local single-operator help desk. Not an internet-facing multi-user service."""

import os, secrets, sqlite3
from pathlib import Path
from flask import Flask, abort, g, redirect, render_template, request, session, url_for

STATUSES = ("Open", "In progress", "Resolved")
CATEGORIES = ("General", "Hardware", "Software", "Network", "Access")

PRIORITIES = ("Low", "Medium", "High", "Critical")


def create_app(config=None):
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parent))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("HELPDESK_DATABASE", str(Path(__file__).with_name("tickets.db"))),
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
            g.db.execute("PRAGMA foreign_keys=ON")
            g.db.execute("PRAGMA busy_timeout=5000")
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
          id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), detail TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)

        # Additive, idempotent migration: existing tickets and history are preserved.
        columns = {r["name"] for r in db().execute("PRAGMA table_info(tickets)")}
        if "category" not in columns:
            db().execute("ALTER TABLE tickets ADD COLUMN category TEXT NOT NULL DEFAULT 'General' CHECK(category IN ('General','Hardware','Software','Network','Access'))")
        db().executescript("""
        CREATE INDEX IF NOT EXISTS ticket_queue ON tickets(status, priority, category);
        CREATE INDEX IF NOT EXISTS ticket_history ON history(ticket_id, id);
        -- Also enforce relationships on legacy history tables without a foreign key.
        CREATE TRIGGER IF NOT EXISTS history_parent_insert BEFORE INSERT ON history
        WHEN NOT EXISTS(SELECT 1 FROM tickets WHERE id=NEW.ticket_id)
        BEGIN SELECT RAISE(ABORT, 'Unknown ticket'); END;
        CREATE TRIGGER IF NOT EXISTS history_parent_update BEFORE UPDATE OF ticket_id ON history
        WHEN NOT EXISTS(SELECT 1 FROM tickets WHERE id=NEW.ticket_id)
        BEGIN SELECT RAISE(ABORT, 'Unknown ticket'); END;
        CREATE TRIGGER IF NOT EXISTS preserve_ticket_history BEFORE DELETE ON tickets
        WHEN EXISTS(SELECT 1 FROM history WHERE ticket_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'Ticket has history'); END;
        """)
        db().commit()

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def request_error(error):
        return render_template("error.html", error=error), error.code

    @app.before_request
    def csrf():
        session.setdefault("csrf", secrets.token_hex(32))
        if request.method == "POST" and not secrets.compare_digest(
            session["csrf"].encode(), request.form.get("csrf", "").encode()
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
        filters = {}
        for field, allowed in (("priority", PRIORITIES), ("category", CATEGORIES)):
            value = request.args.get(field, "")
            if value and value not in allowed:
                abort(400, "Invalid queue filter.")
            filters[field] = value
            if value:
                sql += f" AND {field}=?"  # field comes only from the fixed tuple above
                args.append(value)
        assignee = request.args.get("assignee", "").strip()
        if assignee:
            sql += " AND assignee=?"
            args.append(assignee)
        if status and status not in STATUSES:
            abort(400, "Invalid status filter.")
        try:
            page = int(request.args.get("page", "1"))
            if not 1 <= page <= 1000000:
                raise ValueError
        except ValueError:
            abort(400, "Invalid page number.")
        total = db().execute("SELECT COUNT(*) FROM (" + sql + ")", args).fetchone()[0]
        rows = db().execute(sql + " ORDER BY id DESC LIMIT 25 OFFSET ?", args + [(page - 1) * 25]).fetchall()
        def page_url(number):
            query = request.args.to_dict()
            query["page"] = number
            return url_for("index", **query)
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
            categories=CATEGORIES, filters=filters, assignee=assignee,
            page=page, total=total, page_url=page_url,
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
        category = request.form.get("category", "General")
        if category not in CATEGORIES:
            abort(400, "Invalid category.")
        c = db().execute(
            "INSERT INTO tickets(title,description,requester,priority,category) VALUES (?,?,?,?,?)",
            (*values.values(), category),
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
            category = request.form.get("category", ticket["category"])
            if (
                category not in CATEGORIES
                or status not in STATUSES
                or priority not in PRIORITIES
                or len(assignee) > 120
            ):
                abort(400, "Invalid update.")
            db().execute(
                "UPDATE tickets SET status=?,priority=?,assignee=?,category=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, priority, assignee, category, ticket_id),
            )
            detail = f"Category: {ticket['category']} → {category}; Status: {ticket['status']} → {status}; priority: {ticket['priority']} → {priority}; assignee: {ticket['assignee']} → {assignee}"
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
            categories=CATEGORIES,
            history=history,
            statuses=STATUSES,
            priorities=PRIORITIES,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
