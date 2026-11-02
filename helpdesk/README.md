# IT Help Desk Ticketing Application
Python, Flask, SQLite, and server-rendered HTML/CSS.

## Start
From the repository root, install `requirements.txt`, then:
```sh
python helpdesk/seed.py
python helpdesk/app.py
```
Open http://127.0.0.1:5000. Seeding inserts three synthetic tickets only into an empty database. The database is created automatically and saved at `helpdesk/tickets.db`. Existing tickets survive restarts.

## Features
- Create tickets with title, description, requester and priority.
- Search title, description or requester; filter by status.
- Assign an operator and update priority or status, including reopening resolved tickets.
- Review timestamped activity records.
- View counts for Open, In progress and Resolved.
- Responsive layout, form labels, server validation, parameterized SQL, autoescaped templates, CSRF tokens and basic browser security headers.

## Architecture and limits
`create_app()` supports an alternate database for isolated tests. Each request has its own SQLite connection. Ticket updates and their history are committed together. Search uses SQL LIKE with bound parameters; `%` and `_` are wildcard characters. This small demo loads the matching queue without pagination.

This is a single-operator localhost app, with no login or authorization. History records actions but cannot establish the identity of an authenticated actor. It is not ready for public production use. Add identity management, role checks, HTTPS, pagination, backups, deployment configuration and concurrency testing before external use. The app's random secret resets sessions on restart unless `SECRET_KEY` is supplied through the environment. Never commit a real secret.

## Testing
Run `python -m pytest -q` from the root. Tests cover lifecycle, validation, CSRF rejection, escaping, search, and missing tickets.
