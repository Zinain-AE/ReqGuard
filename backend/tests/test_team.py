import pytest

MEMBER = {"name": "Dana", "email": "dana@example.com", "skills": ["Python", "FastAPI"], "role": "lead"}


@pytest.fixture
def owner(client, make_user):
    """Headers of a project owner and the team URL of their project."""
    _, headers = make_user()
    project = client.post("/projects", json={"name": "Acme"}, headers=headers).json()
    return headers, f"/projects/{project['id']}/team"


def add(client, headers, url, **overrides):
    return client.post(url, json={**MEMBER, **overrides}, headers=headers)


def test_add_and_list_members(client, owner):
    headers, url = owner

    res = add(client, headers, url)

    assert res.status_code == 201
    member = res.json()
    assert member["role"] == "lead"
    assert member["skills"] == ["Python", "FastAPI"]
    assert client.get(url, headers=headers).json() == [member]


def test_skills_are_normalised(client, owner):
    headers, url = owner

    res = add(client, headers, url, skills=["  React ", "react", "", "SQL   databases", "Python"])

    assert res.json()["skills"] == ["React", "SQL databases", "Python"]


def test_skills_limits(client, owner):
    headers, url = owner
    assert add(client, headers, url, skills=["x" * 51]).status_code == 422
    assert add(client, headers, url, skills=[f"s{i}" for i in range(31)]).status_code == 422


def test_invalid_role_is_422(client, owner):
    headers, url = owner
    assert add(client, headers, url, role="manager").status_code == 422


def test_role_and_skills_defaults(client, owner):
    headers, url = owner

    res = client.post(url, json={"name": "Eve", "email": "eve@example.com"}, headers=headers)

    assert res.json()["role"] == "developer"
    assert res.json()["skills"] == []


def test_duplicate_email_in_project_is_409(client, owner):
    headers, url = owner
    add(client, headers, url)

    assert add(client, headers, url, name="Other", email="DANA@example.com").status_code == 409


def test_same_email_allowed_in_different_projects(client, make_user):
    _, headers = make_user()
    p1 = client.post("/projects", json={"name": "P1"}, headers=headers).json()
    p2 = client.post("/projects", json={"name": "P2"}, headers=headers).json()

    assert add(client, headers, f"/projects/{p1['id']}/team").status_code == 201
    assert add(client, headers, f"/projects/{p2['id']}/team").status_code == 201


def test_update_member(client, owner):
    headers, url = owner
    member = add(client, headers, url).json()

    res = client.patch(f"{url}/{member['id']}", json={"role": "qa", "skills": ["pytest"]}, headers=headers)

    assert res.status_code == 200
    assert res.json()["role"] == "qa"
    assert res.json()["skills"] == ["pytest"]
    assert res.json()["name"] == "Dana"


def test_update_to_taken_email_is_409(client, owner):
    headers, url = owner
    add(client, headers, url)
    other = add(client, headers, url, name="Finn", email="finn@example.com").json()

    res = client.patch(f"{url}/{other['id']}", json={"email": "dana@example.com"}, headers=headers)

    assert res.status_code == 409


def test_update_keeping_own_email_is_ok(client, owner):
    headers, url = owner
    member = add(client, headers, url).json()

    res = client.patch(f"{url}/{member['id']}", json={"email": "dana@example.com"}, headers=headers)

    assert res.status_code == 200


def test_delete_member(client, owner):
    headers, url = owner
    member = add(client, headers, url).json()

    assert client.delete(f"{url}/{member['id']}", headers=headers).status_code == 204
    assert client.get(url, headers=headers).json() == []


def test_non_owner_gets_404_everywhere(client, owner, make_user):
    headers, url = owner
    member = add(client, headers, url).json()
    _, stranger = make_user()

    assert client.get(url, headers=stranger).status_code == 404
    assert add(client, stranger, url, email="x@example.com").status_code == 404
    assert client.patch(f"{url}/{member['id']}", json={"role": "qa"}, headers=stranger).status_code == 404
    assert client.delete(f"{url}/{member['id']}", headers=stranger).status_code == 404


def test_member_of_another_project_is_404(client, make_user):
    _, headers = make_user()
    p1 = client.post("/projects", json={"name": "P1"}, headers=headers).json()
    p2 = client.post("/projects", json={"name": "P2"}, headers=headers).json()
    member = add(client, headers, f"/projects/{p1['id']}/team").json()

    wrong_url = f"/projects/{p2['id']}/team/{member['id']}"

    assert client.patch(wrong_url, json={"role": "qa"}, headers=headers).status_code == 404
    assert client.delete(wrong_url, headers=headers).status_code == 404


def test_team_requires_login(client, owner):
    _, url = owner
    assert client.get(url).status_code == 401
