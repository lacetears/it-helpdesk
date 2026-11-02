import importlib.util, json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


helpdesk = module("helpdesk_app", "helpdesk/app.py")


@pytest.fixture
def client(tmp_path):
    app = helpdesk.create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "DATABASE": str(tmp_path / "test.db"),
        }
    )
    return app.test_client()


def csrf(client):
    client.get("/")
    with client.session_transaction() as session:
        return session["csrf"]


def submit(client, **kwargs):
    data = dict(
        title="Printer offline",
        description="Needs investigation",
        requester="Demo",
        priority="High",
        csrf=csrf(client),
    )
    data.update(kwargs)
    return client.post("/tickets", data=data)


def test_ticket_lifecycle(client):
    assert submit(client).status_code == 302
    response = client.post(
        "/tickets/1",
        data=dict(
            csrf=csrf(client), status="Resolved", priority="Low", assignee="Alex"
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Alex" in response.data
    assert b"Ticket created" in response.data
    assert b"Printer offline" in client.get("/?q=Printer&status=Resolved").data
    assert b"Printer offline" not in client.get("/?status=Open").data


def test_csrf(client):
    assert client.post("/tickets", data={"title": "x"}).status_code == 400


def test_invalid_priority(client):
    assert submit(client, priority="Unknown").status_code == 400


def test_xss_escaped(client):
    submit(client, title="<script>alert(1)</script>")
    response = client.get("/tickets/1")
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_sql_injection_search(client):
    submit(client)
    assert client.get("/?q=' OR 1=1 --").status_code == 200
    assert client.get("/tickets/1").status_code == 200


def test_missing_ticket(client):
    assert client.get("/tickets/999").status_code == 404


def test_note_and_validation(client):
    submit(client)
    response = client.post(
        "/tickets/1/notes",
        data={"csrf": csrf(client), "note": "Reinstalled driver"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Note: Reinstalled driver" in response.data
    assert (
        client.post(
            "/tickets/1/notes", data={"csrf": csrf(client), "note": " "}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/tickets/999/notes", data={"csrf": csrf(client), "note": "test"}
        ).status_code
        == 404
    )


def test_persistence_across_app_instances(tmp_path):
    config = {
        "TESTING": True,
        "SECRET_KEY": "test-only",
        "DATABASE": str(tmp_path / "persistent.db"),
    }
    first = helpdesk.create_app(config).test_client()
    submit(first, title="Persisted request")
    second = helpdesk.create_app(config).test_client()
    assert b"Persisted request" in second.get("/tickets/1").data
