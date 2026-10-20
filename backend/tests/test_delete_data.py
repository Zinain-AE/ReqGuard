"""Deleting imported data (NFR-04): one source with its messages, or a single message."""

from pathlib import Path

import pytest

from app.models import Message, Source

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def loaded(client, make_user):
    """Owner headers and project URL, with a WhatsApp chat (5 messages) and an email (1) imported."""
    _, headers = make_user()
    project = client.post("/projects", json={"name": "Acme"}, headers=headers).json()
    base = f"/projects/{project['id']}"
    files = [
        ("files", ("WhatsApp Chat with Acme.txt", (FIXTURES / "whatsapp_android.txt").read_bytes())),
        ("files", ("client_email.eml", (FIXTURES / "client_email.eml").read_bytes())),
    ]
    assert client.post(f"{base}/uploads", files=files, headers=headers).json()["imported"] == 6
    return headers, base


def sources(client, headers, base):
    return {s["type"]: s for s in client.get(f"{base}/sources", headers=headers).json()}


def messages(client, headers, base, **params):
    return client.get(f"{base}/messages", params=params, headers=headers).json()


# ---------- delete a source ----------


def test_delete_source_removes_it_and_its_messages(client, loaded, db_session_factory):
    headers, base = loaded
    whatsapp = sources(client, headers, base)["whatsapp"]

    assert client.delete(f"{base}/sources/{whatsapp['id']}", headers=headers).status_code == 204

    assert set(sources(client, headers, base)) == {"email"}
    remaining = messages(client, headers, base)
    assert remaining["total"] == 1
    assert remaining["items"][0]["source"] == "email"
    db = db_session_factory()
    assert db.query(Message).filter(Message.source_id == whatsapp["id"]).count() == 0
    assert db.query(Message).filter(Message.source_id.is_(None)).count() == 0  # nothing left behind
    db.close()


def test_reupload_after_delete_imports_again(client, loaded):
    headers, base = loaded
    whatsapp = sources(client, headers, base)["whatsapp"]
    client.delete(f"{base}/sources/{whatsapp['id']}", headers=headers)

    files = [("files", ("WhatsApp Chat with Acme.txt", (FIXTURES / "whatsapp_android.txt").read_bytes()))]
    body = client.post(f"{base}/uploads", files=files, headers=headers).json()

    assert (body["imported"], body["duplicates"]) == (5, 0)


def test_delete_unknown_source_is_404(client, loaded):
    headers, base = loaded
    assert client.delete(f"{base}/sources/9999", headers=headers).status_code == 404


def test_delete_source_of_another_project_is_404(client, loaded):
    headers, base = loaded
    whatsapp = sources(client, headers, base)["whatsapp"]
    other = client.post("/projects", json={"name": "Other"}, headers=headers).json()

    res = client.delete(f"/projects/{other['id']}/sources/{whatsapp['id']}", headers=headers)

    assert res.status_code == 404
    assert messages(client, headers, base)["total"] == 6


def test_delete_source_by_other_user_is_404(client, loaded, make_user):
    headers, base = loaded
    whatsapp = sources(client, headers, base)["whatsapp"]
    _, stranger = make_user()

    assert client.delete(f"{base}/sources/{whatsapp['id']}", headers=stranger).status_code == 404
    assert messages(client, headers, base)["total"] == 6


def test_delete_source_requires_login(client, loaded):
    headers, base = loaded
    whatsapp = sources(client, headers, base)["whatsapp"]
    assert client.delete(f"{base}/sources/{whatsapp['id']}").status_code == 401


# ---------- delete one message ----------


def test_delete_single_message(client, loaded):
    headers, base = loaded
    target = messages(client, headers, base, source="whatsapp")["items"][0]

    assert client.delete(f"{base}/messages/{target['id']}", headers=headers).status_code == 204

    after = messages(client, headers, base)
    assert after["total"] == 5
    assert target["id"] not in {m["id"] for m in after["items"]}
    # The source stays, with one message less
    assert sources(client, headers, base)["whatsapp"]["message_count"] == 4


def test_delete_message_twice_is_404(client, loaded):
    headers, base = loaded
    target = messages(client, headers, base)["items"][0]
    client.delete(f"{base}/messages/{target['id']}", headers=headers)

    assert client.delete(f"{base}/messages/{target['id']}", headers=headers).status_code == 404


def test_delete_message_of_another_project_is_404(client, loaded):
    headers, base = loaded
    target = messages(client, headers, base)["items"][0]
    other = client.post("/projects", json={"name": "Other"}, headers=headers).json()

    assert client.delete(f"/projects/{other['id']}/messages/{target['id']}", headers=headers).status_code == 404
    assert messages(client, headers, base)["total"] == 6


def test_delete_message_by_other_user_is_404(client, loaded, make_user):
    headers, base = loaded
    target = messages(client, headers, base)["items"][0]
    _, stranger = make_user()

    assert client.delete(f"{base}/messages/{target['id']}", headers=stranger).status_code == 404
    assert messages(client, headers, base)["total"] == 6


def test_delete_message_requires_login(client, loaded):
    headers, base = loaded
    target = messages(client, headers, base)["items"][0]
    assert client.delete(f"{base}/messages/{target['id']}").status_code == 401


# ---------- delete the whole project ----------


def test_deleting_project_cascades_to_sources_and_messages(client, loaded, make_user, db_session_factory):
    headers, base = loaded
    # A second user's data must survive
    _, other_headers = make_user()
    other = client.post("/projects", json={"name": "Keep"}, headers=other_headers).json()
    files = [("files", ("notes.md", b"Keep this paragraph."))]
    client.post(f"/projects/{other['id']}/uploads", files=files, headers=other_headers)

    assert client.delete(base, headers=headers).status_code == 204

    db = db_session_factory()
    assert db.query(Source).count() == 1
    assert db.query(Message).count() == 1
    assert db.query(Message).one().project_id == other["id"]
    db.close()
