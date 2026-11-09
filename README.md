# IT Help Desk

A local support queue for recording requests, assigning work, and preserving investigation notes. Built with Python, Flask, SQLite, and server-rendered HTML/CSS.

## Support workflow

Create a ticket with a requester, description, priority and category (General, Hardware, Software, Network, Access). Assign it, move it between Open, In progress and Resolved, and record work notes. Reopening is allowed. Search by title, description or requester; combine status, priority, category and exact-assignee filters. The queue displays 25 tickets per page and preserves filters across pages. Status totals describe the entire queue, not just the filtered slice.

## Run locally

Python 3.12 or 3.13:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python helpdesk/seed.py
python helpdesk/app.py
```

Open http://127.0.0.1:5000. Seeding preserves existing tickets. All seed records are fictional.
Optional `HELPDESK_DATABASE` sets the SQLite path; its parent directory must exist.
`SECRET_KEY` can persist sessions across restarts. Without it a random key is created at startup.

## Architecture and decisions

`helpdesk/app.py` exposes an application factory, request-scoped connections, parameterized SQL and route handlers. Jinja templates escape ticket content. Ticket mutations and their history records commit together. The small codebase deliberately keeps routes together; a service/repository split becomes worthwhile when authentication or integrations introduce more business logic.

Startup performs an additive category migration and creates queue/history indexes. Existing records default to General. Foreign keys protect new databases; triggers also protect legacy history relationships without rebuilding tables or deleting data. Existing historical orphans, if any, are not silently removed.

A per-session CSRF token protects forms. Responses include a restrictive content security policy and MIME-sniffing protection. Field sizes, enum values and request-body size are checked server-side; validation errors render a readable page. Use the browser Back button to recover entered form values after an error.

## Walkthrough

1. Create “VPN disconnects during calls,” category Network, priority High.
2. Assign Alex, set In progress, and record checks performed.
3. Add a resolution note and mark Resolved.
4. Filter by Network, Resolved and Alex, then inspect the history.

## Verification

```sh
python -m pytest -q
```

Tests cover lifecycle, persistent storage, additive legacy migration, invalid fields, Unicode CSRF input, XSS escaping, parameterized search, categories, assignment, pagination, notes, missing records, security headers and body limits. CI runs Python 3.12 and 3.13.

## Demo and deployment boundary

[Earlier browser-only demo](https://lacetears.github.io/it-career-portfolio/helpdesk.html) uses browser storage, not Flask or SQLite. Its [existing screenshot](docs/screenshot.jpg) illustrates that separate demo and does not show every feature on this branch.

This is a **single-operator localhost lab**, not a production service. There is no login, authorization, verified actor identity, SLA engine or notification delivery. History is an operational record, not a tamper-proof audit log. Concurrent edits are last-write-wins. Flask's development server is used only on localhost. Public hosting requires authentication/authorization, HTTPS, stable secret management, secure cookies, a production WSGI server, backups and a deployment review. No deployment or load-test claim is made.

## Next engineering steps

Add authenticated roles, conflict detection for concurrent edits, structured resolution fields and tested backup/restore procedures before expanding deployment. See [security notes](SECURITY.md).
