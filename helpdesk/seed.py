from app import create_app
import sqlite3

app = create_app()
with sqlite3.connect(app.config["DATABASE"]) as db:
    if db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]:
        print("Existing tickets preserved; no demo rows inserted.")
    else:
        db.executemany(
            "INSERT INTO tickets(title,description,requester,assignee,priority,status) VALUES (?,?,?,?,?,?)",
            [
                (
                    "VPN disconnects during calls",
                    "Synthetic ticket: VPN reconnects every 15 minutes. Check client logs and network stability.",
                    "Jordan Lee",
                    "Alex",
                    "High",
                    "In progress",
                ),
                (
                    "New employee laptop setup",
                    "Synthetic ticket: prepare standard applications and verify device enrollment.",
                    "Morgan Chen",
                    "",
                    "Medium",
                    "Open",
                ),
                (
                    "Printer unavailable on second floor",
                    "Synthetic ticket: print queue cleared and test page confirmed.",
                    "Taylor Reed",
                    "Alex",
                    "Low",
                    "Resolved",
                ),
            ],
        )
        db.execute(
            "INSERT INTO history(ticket_id,detail) SELECT id,'Synthetic demo ticket imported' FROM tickets"
        )
        print("Created 3 synthetic demo tickets.")
