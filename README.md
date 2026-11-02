# IT Help Desk

A local ticket tracker for a support technician: capture a request, set its priority, assign an owner, and follow it through resolution.

**Python · Flask · SQLite · HTML/CSS**

## Try it
```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python helpdesk/seed.py
python helpdesk/app.py
```
Open http://127.0.0.1:5000. The seed command adds three example tickets only if the database is empty.

## A two-minute walkthrough
1. Create a ticket for an intermittent VPN connection. Set priority to High.
2. Assign it to a technician and change the status to In progress.
3. Add a resolution note, then mark the request Resolved.
4. Search for VPN in the queue and filter to Resolved.
5. Open the ticket to review the recorded changes.

## What works
Ticket creation, assignment, four priority levels, three statuses, search, status filters, timestamped history, and persistent SQLite storage. Forms validate input on the server. SQL uses bound parameters, HTML templates escape user content, and state changes require CSRF tokens.

## How it is put together
`helpdesk/app.py` owns the routes and database access. Templates are in `helpdesk/templates`; CSS is in `helpdesk/static`. A fresh database is created on startup. Updates and history entries commit together. Tests use a temporary database so they do not alter demo tickets.

SQLite keeps the project easy to run and inspect. Server-rendered pages keep the request flow simple. This version intentionally targets one local operator; authentication and multiple permission levels would be the next architectural change.

## Test
```sh
python -m pytest -q
```
The suite covers the ticket lifecycle, notes, persistence, input validation, CSRF, escaping, search, and missing tickets.

## Limits
This application has no login, authorization, email delivery, or SLA engine. Run it on localhost; do not deploy it publicly as a help desk for real users. It has not been load-tested. All seeded tickets are fictional.

[Development notes](docs/development.md) · [Detailed setup](helpdesk/README.md)
