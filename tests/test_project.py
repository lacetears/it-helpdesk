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


def test_unicode_csrf_returns_400(client):
    assert client.post('/tickets', data={'csrf': 'é'}).status_code == 400


@pytest.mark.parametrize('field,value', [('title',' '), ('description','x'*5001), ('requester','x'*121), ('category','Invalid')])
def test_invalid_fields_do_not_create_ticket(client, field, value):
    assert submit(client, **{field:value}).status_code == 400
    assert client.get('/tickets/1').status_code == 404


def test_category_filters_and_pagination(client):
    for i in range(26):
        submit(client, title=f'Network issue {i}', category='Network')
    submit(client, title='Hardware issue', category='Hardware')
    first = client.get('/?category=Network&priority=High')
    assert b'26 matching tickets' in first.data
    assert b'Hardware issue' not in first.data
    assert b'Network issue 0</a>' not in first.data
    assert b'Network issue 0</a>' in client.get('/?category=Network&page=2').data
    assert client.get('/?page=zero').status_code == 400
    assert client.get('/?category=invalid').status_code == 400


def test_category_assignment_history(client):
    submit(client)
    response=client.post('/tickets/1', data=dict(csrf=csrf(client),status='In progress',priority='Critical',assignee='Alex',category='Network'),follow_redirects=True)
    assert b'General' in response.data and b'Network' in response.data
    assert b'Printer offline' in client.get('/?assignee=Alex&category=Network&priority=Critical').data
    assert b'Printer offline' not in client.get('/?assignee=Other').data


def test_legacy_database_migration(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE tickets(id INTEGER PRIMARY KEY,title TEXT,description TEXT,requester TEXT,assignee TEXT,priority TEXT,status TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE history(id INTEGER PRIMARY KEY,ticket_id INTEGER,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP); INSERT INTO tickets VALUES(7,'Legacy','Description','Demo','','High','Open','',''); INSERT INTO history(ticket_id,detail) VALUES(7,'Original note');")
    for _ in range(2):
        app=helpdesk.create_app(dict(TESTING=True,DATABASE=str(path)))
        response=app.test_client().get('/tickets/7')
        assert b'Legacy' in response.data and b'Original note' in response.data
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT category FROM tickets').fetchone()[0]=='General'
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO history(ticket_id,detail) VALUES(99,'orphan')")


def test_security_headers_and_size_limit(client):
    response=client.get('/')
    assert response.headers['X-Content-Type-Options']=='nosniff'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert client.post('/tickets',data={'description':'x'*40000}).status_code==413
