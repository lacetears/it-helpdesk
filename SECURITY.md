# Security boundary

Local, single-operator demonstration only. Any person who can reach the server can read and modify tickets; CSRF is not authentication. Bind localhost and use fictional data. SQL parameters, template escaping, per-session CSRF, request limits and headers are defense-in-depth, not a production certification.

SQLite files and `.env` are ignored. Never commit real tickets, credentials or tokens. History has no verified actor identity and can be edited by a database administrator. Existing orphan history is preserved during migration for investigation. Back up the database while the app is stopped before upgrading; restoring the whole backup is the rollback strategy. Automated migration tests cover legacy ticket/note retention, not operational backup recovery.

Public deployment and multiple workers require a separate design review. No vulnerability scan, penetration test or load test has been performed.
