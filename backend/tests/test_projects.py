from sqlalchemy import func, select

from app.models import TeamMember

PROJECT = {"name": "Acme portal", "description": "Client portal", "scope_text": "Login, orders, invoices"}


def create_project(client, headers, **overrides):
    res = client.post("/projects", json={**PROJECT, **overrides}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_project_endpoints_require_login(client):
    assert client.get("/projects").status_code == 401
    assert client.post("/projects", json=PROJECT).status_code == 401
    assert client.get("/projects/1").status_code == 401


def test_create_and_get_project(client, make_user):
    user, headers = make_user()

    project = create_project(client, headers)

    assert project["owner_id"] == user["id"]
    assert project["scope_text"] == PROJECT["scope_text"]
    assert client.get(f"/projects/{project['id']}", headers=headers).json() == project


def test_create_project_requires_name(client, make_user):
    _, headers = make_user()
    assert client.post("/projects", json={"name": "  "}, headers=headers).status_code == 422


def test_list_shows_only_own_projects(client, make_user):
    _, alice = make_user()
    _, bob = make_user()
    create_project(client, alice, name="Alice 1")
    create_project(client, alice, name="Alice 2")
    create_project(client, bob, name="Bob 1")

    names = [p["name"] for p in client.get("/projects", headers=alice).json()]

    assert sorted(names) == ["Alice 1", "Alice 2"]


def test_other_user_cannot_read_update_or_delete(client, make_user):
    _, alice = make_user()
    _, bob = make_user()
    project = create_project(client, alice)
    url = f"/projects/{project['id']}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"name": "Hacked"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    # Unchanged for the owner
    assert client.get(url, headers=alice).json()["name"] == PROJECT["name"]


def test_missing_project_is_404(client, make_user):
    _, headers = make_user()
    assert client.get("/projects/999", headers=headers).status_code == 404


def test_owner_can_update_only_sent_fields(client, make_user):
    _, headers = make_user()
    project = create_project(client, headers)

    res = client.patch(f"/projects/{project['id']}", json={"description": "New text"}, headers=headers)

    assert res.status_code == 200
    assert res.json()["description"] == "New text"
    assert res.json()["name"] == PROJECT["name"]


def test_owner_can_delete_and_team_is_deleted(client, make_user, db_session_factory):
    _, headers = make_user()
    project = create_project(client, headers)
    client.post(
        f"/projects/{project['id']}/team",
        json={"name": "Dev", "email": "dev@example.com", "role": "developer"},
        headers=headers,
    )

    res = client.delete(f"/projects/{project['id']}", headers=headers)

    assert res.status_code == 204
    assert client.get(f"/projects/{project['id']}", headers=headers).status_code == 404
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TeamMember)) == 0
