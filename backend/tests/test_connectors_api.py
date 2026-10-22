"""API connector endpoints: configured check, create, sync (twice, no duplicates), status, Gmail OAuth.

External APIs are mocked with respx; the test client itself does not go through respx.
"""

from urllib.parse import parse_qs, urlparse

import pytest
import respx
from cryptography.fernet import Fernet

from app.connectors.gmail import API as GMAIL_API
from app.connectors.gmail import TOKEN_URL
from app.connectors.slack import API as SLACK_API
from app.core.config import settings
from app.core.security import create_oauth_state
from app.models import Source
from tests.conftest import api_json

SLACK_TOKEN = "xoxb-very-secret-slack-token"
TELEGRAM_TOKEN = "123456:very-secret-telegram-token"
GOOGLE_SECRET = "very-secret-google-client-secret"
SECRETS = (SLACK_TOKEN, TELEGRAM_TOKEN, GOOGLE_SECRET, "1//test-refresh-token")

CONNECTOR_ENV = (
    "jira_base_url",
    "jira_email",
    "jira_api_token",
    "slack_bot_token",
    "telegram_bot_token",
    "discord_bot_token",
    "google_client_id",
    "google_client_secret",
    "token_encryption_key",
)


@pytest.fixture(autouse=True)
def no_connector_env(monkeypatch):
    """Ignore whatever is in the developer's backend/.env."""
    for name in CONNECTOR_ENV:
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(settings, "frontend_url", "http://frontend.test")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://backend.test/oauth/gmail/callback")


@pytest.fixture
def slack_env(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", SLACK_TOKEN)


@pytest.fixture
def gmail_env(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", GOOGLE_SECRET)
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())


@pytest.fixture
def owner(client, make_user):
    user, headers = make_user()
    project = client.post("/projects", json={"name": "Acme"}, headers=headers).json()
    return user, headers, project["id"]


def assert_no_secrets(response):
    for secret in SECRETS:
        assert secret not in response.text


def mock_slack(router: respx.Router):
    router.get(f"{SLACK_API}/conversations.list").respond(json=api_json("slack/conversations_list_page2.json"))
    history = {**api_json("slack/history_page1.json"), "response_metadata": {"next_cursor": ""}}
    router.get(f"{SLACK_API}/conversations.history").respond(json=history)
    router.get(f"{SLACK_API}/conversations.replies").respond(json=api_json("slack/replies.json"))


def create_slack(client, headers, project_id, name="Acme Slack"):
    return client.post(
        f"/projects/{project_id}/sources",
        json={"type": "slack", "display_name": name, "settings": {"channels": ["#client-acme"]}},
        headers=headers,
    )


# ---------- Configured or not ----------


def test_connectors_not_configured(client, owner):
    _, headers, _ = owner
    res = client.get("/connectors", headers=headers)
    assert res.status_code == 200
    by_type = {c["type"]: c for c in res.json()}
    assert set(by_type) == {"jira", "slack", "gmail", "telegram", "discord"}
    assert not any(c["configured"] for c in by_type.values())
    assert by_type["jira"]["missing_env"] == ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
    assert by_type["gmail"]["missing_env"] == ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "TOKEN_ENCRYPTION_KEY"]


def test_connectors_configured_without_revealing_values(client, owner, slack_env, gmail_env, monkeypatch):
    _, headers, _ = owner
    monkeypatch.setattr(settings, "telegram_bot_token", TELEGRAM_TOKEN)
    res = client.get("/connectors", headers=headers)
    by_type = {c["type"]: c for c in res.json()}
    assert by_type["slack"] == {"type": "slack", "label": "Slack", "configured": True, "missing_env": []}
    assert by_type["telegram"]["configured"] and by_type["gmail"]["configured"]
    assert not by_type["discord"]["configured"]
    assert_no_secrets(res)


def test_invalid_encryption_key_counts_as_missing(client, owner, gmail_env, monkeypatch):
    _, headers, _ = owner
    monkeypatch.setattr(settings, "token_encryption_key", "not-a-fernet-key")
    gmail = next(c for c in client.get("/connectors", headers=headers).json() if c["type"] == "gmail")
    assert gmail["missing_env"] == ["TOKEN_ENCRYPTION_KEY"]


def test_connectors_require_login(client):
    assert client.get("/connectors").status_code == 401


# ---------- Create ----------


def test_create_without_token_is_not_configured(client, owner):
    _, headers, project_id = owner
    res = create_slack(client, headers, project_id)
    assert res.status_code == 400
    assert res.json()["detail"] == "Not configured: set SLACK_BOT_TOKEN in backend/.env."


def test_create_source(client, owner, slack_env):
    _, headers, project_id = owner
    res = create_slack(client, headers, project_id)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "slack"
    assert body["config"] == {"origin": "api", "settings": {"channels": ["client-acme"]}, "state": {}}
    assert body["sync_status"] is None and body["needs_auth"] is False
    assert "credentials_encrypted" not in body
    assert_no_secrets(res)

    assert create_slack(client, headers, project_id).status_code == 409


def test_create_with_invalid_settings(client, owner, slack_env):
    _, headers, project_id = owner
    res = client.post(
        f"/projects/{project_id}/sources",
        json={"type": "slack", "display_name": "x", "settings": {"channels": []}},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Choose at least one Slack channel" in res.json()["detail"]

    res = client.post(
        f"/projects/{project_id}/sources", json={"type": "whatsapp", "display_name": "x"}, headers=headers
    )
    assert res.status_code == 400


# ---------- Sync and status ----------


@respx.mock
def test_sync_twice_does_not_duplicate(client, owner, slack_env):
    _, headers, project_id = owner
    mock_slack(respx.mock)
    source_id = create_slack(client, headers, project_id).json()["id"]

    first = client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["imported"] == 3  # parent + 2 thread replies (join message skipped)
    assert first.json()["sync_status"] == "ok"
    assert_no_secrets(first)

    second = client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=headers)
    assert second.json()["imported"] == 0
    assert second.json()["duplicates"] == 3

    messages = client.get(f"/projects/{project_id}/messages?source=slack", headers=headers).json()
    assert messages["total"] == 3

    status = client.get(f"/projects/{project_id}/sources/{source_id}/status", headers=headers)
    assert status.status_code == 200
    body = status.json()
    assert body["configured"] is True
    assert body["sync_status"] == "ok" and body["sync_error"] is None
    assert body["message_count"] == 3
    assert body["last_synced_at"] is not None

    listed = client.get(f"/projects/{project_id}/sources", headers=headers)
    assert listed.json()[0]["message_count"] == 3
    assert_no_secrets(listed)


@respx.mock
def test_sync_error_is_stored_and_reported(client, owner, slack_env):
    _, headers, project_id = owner
    respx.get(f"{SLACK_API}/conversations.list").respond(json=api_json("slack/error_invalid_auth.json"))
    source_id = create_slack(client, headers, project_id).json()["id"]

    res = client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=headers)
    assert res.status_code == 502
    assert "SLACK_BOT_TOKEN" in res.json()["detail"]
    assert_no_secrets(res)

    status = client.get(f"/projects/{project_id}/sources/{source_id}/status", headers=headers).json()
    assert status["sync_status"] == "error"
    assert "SLACK_BOT_TOKEN" in status["sync_error"]


def test_sync_after_token_removed_is_not_configured(client, owner, slack_env, monkeypatch):
    _, headers, project_id = owner
    source_id = create_slack(client, headers, project_id).json()["id"]
    monkeypatch.setattr(settings, "slack_bot_token", None)
    res = client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=headers)
    assert res.status_code == 400
    assert res.json()["detail"].startswith("Not configured")
    status = client.get(f"/projects/{project_id}/sources/{source_id}/status", headers=headers).json()
    assert status["configured"] is False


@respx.mock
def test_telegram_state_saved_between_syncs(client, owner, monkeypatch):
    _, headers, project_id = owner
    monkeypatch.setattr(settings, "telegram_bot_token", TELEGRAM_TOKEN)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    route = respx.get(url)
    route.side_effect = [
        respx.MockResponse(200, json=api_json("telegram/get_updates.json")),
        respx.MockResponse(200, json=api_json("telegram/get_updates_empty.json")),
    ]
    source = client.post(
        f"/projects/{project_id}/sources",
        json={"type": "telegram", "display_name": "Acme group", "settings": {"chat_ids": ["-1001234567890"]}},
        headers=headers,
    ).json()

    first = client.post(f"/projects/{project_id}/sources/{source['id']}/sync", headers=headers)
    assert first.json()["imported"] == 2
    assert_no_secrets(first)
    second = client.post(f"/projects/{project_id}/sources/{source['id']}/sync", headers=headers)
    assert second.json()["imported"] == 0
    assert route.calls[1].request.url.params["offset"] == "503900006"

    listed = client.get(f"/projects/{project_id}/sources", headers=headers).json()
    assert listed[0]["config"]["state"] == {"last_update_id": 503900005}


def test_uploaded_source_cannot_be_synced(client, owner):
    _, headers, project_id = owner
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"files": ("notes.md", b"# Meeting\n\nThe app must support dark mode.\n", "text/markdown")},
        headers=headers,
    )
    source_id = client.get(f"/projects/{project_id}/sources", headers=headers).json()[0]["id"]
    assert upload.status_code == 200
    res = client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=headers)
    assert res.status_code == 400
    status = client.get(f"/projects/{project_id}/sources/{source_id}/status", headers=headers).json()
    assert status["configured"] is True and status["sync_status"] is None


def test_other_users_source_is_404(client, owner, make_user, slack_env):
    _, headers, project_id = owner
    source_id = create_slack(client, headers, project_id).json()["id"]
    _, other_headers = make_user()
    other_project = client.post("/projects", json={"name": "Other"}, headers=other_headers).json()["id"]

    assert client.post(f"/projects/{project_id}/sources/{source_id}/sync", headers=other_headers).status_code == 404
    assert client.get(f"/projects/{project_id}/sources/{source_id}/status", headers=other_headers).status_code == 404
    assert (
        client.post(f"/projects/{other_project}/sources/{source_id}/sync", headers=other_headers).status_code == 404
    )


# ---------- Gmail OAuth ----------


def create_gmail(client, headers, project_id):
    return client.post(
        f"/projects/{project_id}/sources",
        json={"type": "gmail", "display_name": "Acme mail", "settings": {"query": "from:acme.example.com"}},
        headers=headers,
    ).json()


def test_gmail_needs_auth_before_sync(client, owner, gmail_env):
    _, headers, project_id = owner
    source = create_gmail(client, headers, project_id)
    assert source["needs_auth"] is True
    assert source["sync_status"] == "needs_auth"
    res = client.post(f"/projects/{project_id}/sources/{source['id']}/sync", headers=headers)
    assert res.status_code == 409
    assert "Connect a Google account" in res.json()["detail"]


@respx.mock
def test_gmail_oauth_flow_and_sync(client, owner, gmail_env, db_session_factory):
    _, headers, project_id = owner
    source = create_gmail(client, headers, project_id)

    res = client.get(f"/projects/{project_id}/sources/{source['id']}/gmail/authorize", headers=headers)
    assert res.status_code == 200
    url = urlparse(res.json()["url"])
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.netloc == "accounts.google.com"
    assert params["redirect_uri"] == "http://backend.test/oauth/gmail/callback"
    assert_no_secrets(res)

    respx.post(TOKEN_URL).respond(json=api_json("gmail/token_exchange.json"))
    callback = client.get(
        "/oauth/gmail/callback", params={"code": "auth-code", "state": params["state"]}, follow_redirects=False
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "http://frontend.test/sources?gmail=connected"

    with db_session_factory() as db:
        stored = db.get(Source, source["id"]).credentials_encrypted
    assert stored and "test-refresh-token" not in stored

    listed = client.get(f"/projects/{project_id}/sources", headers=headers)
    assert listed.json()[0]["needs_auth"] is False
    assert_no_secrets(listed)

    respx.routes.clear()
    respx.post(TOKEN_URL).respond(json=api_json("gmail/token_refresh.json"))
    respx.get(f"{GMAIL_API}/threads").respond(json=api_json("gmail/threads_page2.json"))
    respx.get(f"{GMAIL_API}/threads/18f0aaaaaaaaaaaa").respond(json=api_json("gmail/thread_2.json"))
    sync = client.post(f"/projects/{project_id}/sources/{source['id']}/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["imported"] == 1


@respx.mock
def test_gmail_revoked_token_asks_to_connect_again(client, owner, gmail_env, db_session_factory):
    from app.core.crypto import encrypt

    _, headers, project_id = owner
    source = create_gmail(client, headers, project_id)
    with db_session_factory() as db:
        db.get(Source, source["id"]).credentials_encrypted = encrypt("1//old-token")
        db.commit()

    respx.post(TOKEN_URL).respond(400, json=api_json("gmail/token_invalid_grant.json"))
    res = client.post(f"/projects/{project_id}/sources/{source['id']}/sync", headers=headers)
    assert res.status_code == 409
    listed = client.get(f"/projects/{project_id}/sources", headers=headers).json()[0]
    assert listed["needs_auth"] is True and listed["sync_status"] == "needs_auth"


def test_gmail_callback_rejects_bad_state(client, owner, gmail_env, make_user):
    user, headers, project_id = owner
    source = create_gmail(client, headers, project_id)

    def callback(state: str):
        return client.get("/oauth/gmail/callback", params={"code": "c", "state": state}, follow_redirects=False)

    assert callback("garbage").headers["location"].endswith("?gmail=error")
    # A login token is not an OAuth state
    login_token = headers["Authorization"].removeprefix("Bearer ")
    assert callback(login_token).headers["location"].endswith("?gmail=error")
    # State made for another user
    other, _ = make_user()
    assert callback(create_oauth_state(other["id"], source["id"])).headers["location"].endswith("?gmail=error")


def test_oauth_state_is_not_a_login_token(client, owner, gmail_env):
    user, _, _ = owner
    state = create_oauth_state(user["id"], 1)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {state}"}).status_code == 401


def test_gmail_callback_denied(client, owner, gmail_env):
    user, headers, project_id = owner
    source = create_gmail(client, headers, project_id)
    res = client.get(
        "/oauth/gmail/callback",
        params={"error": "access_denied", "state": create_oauth_state(user["id"], source["id"])},
        follow_redirects=False,
    )
    assert res.headers["location"] == "http://frontend.test/sources?gmail=denied"
    status = client.get(f"/projects/{project_id}/sources/{source['id']}/status", headers=headers).json()
    assert status["needs_auth"] is True
    assert status["sync_error"] == "Google access was not granted."
