"""Gmail connector (Gmail REST API with OAuth 2.0, read-only scope).

Flow: the user clicks "Connect Google account" → Google consent page → our callback receives a code →
`exchange_code` turns it into a refresh token, which the API stores encrypted on the Source.
On sync the refresh token is exchanged for a short-lived access token, the threads matching the
user's search query (e.g. "from:client@acme.com") are listed, and every message becomes plain text.

Note: while the Google OAuth client is in "Testing" mode, Google expires refresh tokens after 7 days;
the source then shows "Connect Google account" again.
"""

import base64
import re
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, field_validator

from app.connectors.base import NormalizedMessage
from app.connectors.files import clean_email_body, html_to_text, thread_subject
from app.connectors.http import (
    MAX_PAGES,
    TIMEOUT,
    ApiConnector,
    ConnectorError,
    NeedsAuthError,
    json_body,
    send,
)

SOURCE = "gmail"
SERVICE = "Gmail"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_HINT = "Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env."
PAGE_SIZE = 100
SINCE_MARGIN = timedelta(days=1)

_CHARSET_RE = re.compile(r"charset\s*=\s*\"?([\w.:-]+)", re.IGNORECASE)


class GmailSettings(BaseModel):
    # Gmail search syntax, e.g. "from:client@acme.com" or "label:client-acme"
    query: str

    @field_validator("query")
    @classmethod
    def check_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter a Gmail search query, e.g. from:client@acme.com")
        if len(value) > 500:
            raise ValueError("The search query is too long (max 500 characters)")
        return value


def authorize_url(state: str, *, client_id: str, redirect_uri: str) -> str:
    """Google consent page. access_type=offline + prompt=consent so Google always returns a refresh token."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _token_request(client: httpx.Client, data: dict[str, str]) -> dict:
    response = send(
        client, "POST", TOKEN_URL, service="Google", auth_hint=AUTH_HINT, data=data, allow_status=(400, 401)
    )
    body = json_body(response, "Google")
    if response.status_code in (400, 401):
        error = str(body.get("error") or "")
        if error == "invalid_grant":
            raise NeedsAuthError("Google access expired or was revoked. Connect the Google account again.")
        if error in ("invalid_client", "unauthorized_client"):
            raise ConnectorError(f"Google rejected the OAuth client. {AUTH_HINT}")
        raise ConnectorError(f"Google sign-in failed ({error or f'HTTP {response.status_code}'}).")
    return body


def exchange_code(
    code: str, *, client_id: str, client_secret: str, redirect_uri: str, client: httpx.Client | None = None
) -> str:
    """Trade the code from the OAuth callback for a refresh token."""
    http_client = client or httpx.Client(timeout=TIMEOUT)
    try:
        body = _token_request(
            http_client,
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    finally:
        if client is None:
            http_client.close()
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise ConnectorError(
            "Google did not return a refresh token. Remove the app's access in your Google account "
            "settings and connect again."
        )
    return str(refresh_token)


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------


def _headers(part: dict) -> dict[str, str]:
    return {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in part.get("headers") or []}


def _find_part(part: dict, mime_type: str) -> dict | None:
    """First part of this MIME type with inline data (attachments are skipped)."""
    if part.get("mimeType") == mime_type and (part.get("body") or {}).get("data") and not part.get("filename"):
        return part
    for child in part.get("parts") or []:
        found = _find_part(child, mime_type)
        if found is not None:
            return found
    return None


def _decode(part: dict) -> str:
    data = part["body"]["data"]
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    match = _CHARSET_RE.search(_headers(part).get("content-type", ""))
    try:
        return raw.decode(match.group(1) if match else "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def message_body(payload: dict) -> str:
    """Plain text of a Gmail message payload: text/plain if present, else text/html converted."""
    plain = _find_part(payload, "text/plain")
    if plain is not None:
        return _decode(plain)
    html_part = _find_part(payload, "text/html")
    return html_to_text(_decode(html_part)) if html_part is not None else ""


def _author(from_header: str) -> str:
    addresses = getaddresses([from_header])
    if addresses and any(addresses[0]):
        name, address = addresses[0]
        return name or address
    return from_header.strip()


class GmailConnector(ApiConnector):
    source = SOURCE
    label = "Gmail"
    required_env = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "TOKEN_ENCRYPTION_KEY")
    Settings = GmailSettings

    def __init__(
        self,
        settings: GmailSettings,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        client: httpx.Client | None = None,
        state: dict | None = None,
    ):
        super().__init__(client, state)
        self.settings = settings
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

    def _access_token(self) -> str:
        body = _token_request(
            self.client,
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token = body.get("access_token")
        if not token:
            raise ConnectorError("Google did not return an access token.")
        return str(token)

    def _get(self, path: str, params: dict[str, Any], headers: dict[str, str]) -> Any:
        response = send(
            self.client, "GET", f"{API}{path}", service=SERVICE,
            auth_hint="Connect the Google account again.", params=params, headers=headers,
        )
        return json_body(response, SERVICE)

    def _thread_ids(self, query: str, headers: dict[str, str]) -> list[str]:
        ids: list[str] = []
        params: dict[str, Any] = {"q": query, "maxResults": PAGE_SIZE}
        for _ in range(MAX_PAGES):
            data = self._get("/threads", params, headers)
            ids.extend(str(t["id"]) for t in data.get("threads") or [])
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        return ids

    def _thread_messages(self, thread: dict) -> list[NormalizedMessage]:
        messages: list[NormalizedMessage] = []
        items = sorted(thread.get("messages") or [], key=lambda m: int(m.get("internalDate") or 0))
        for index, item in enumerate(items):
            if "DRAFT" in (item.get("labelIds") or []):
                continue
            payload = item.get("payload") or {}
            headers = _headers(payload)
            subject = " ".join(headers.get("subject", "").split())
            original_body = message_body(payload)
            body = clean_email_body(original_body)
            # The subject is part of the text only for the first message; replies repeat it as "Re: ..."
            text = f"{subject}\n\n{body}".strip() if index == 0 and subject else body
            if not text:
                continue
            messages.append(
                NormalizedMessage(
                    source=SOURCE,
                    external_id=str(item["id"]),
                    channel=thread_subject(subject) or "(no subject)",
                    author=_author(headers.get("from", "")),
                    sent_at=datetime.fromtimestamp(int(item["internalDate"]) / 1000, tz=timezone.utc),
                    text=text,
                    raw={
                        "message_id": item["id"],
                        "thread_id": item.get("threadId", thread.get("id")),
                        "label_ids": item.get("labelIds") or [],
                        "from": headers.get("from", ""),
                        "to": headers.get("to", ""),
                        "cc": headers.get("cc", ""),
                        "date": headers.get("date", ""),
                        "subject": subject,
                        "body": original_body,
                    },
                )
            )
        return messages

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        query = self.settings.query
        if since is not None:
            query += f" after:{int((since - SINCE_MARGIN).timestamp())}"
        messages: list[NormalizedMessage] = []
        for thread_id in self._thread_ids(query, headers):
            thread = self._get(f"/threads/{thread_id}", {"format": "full"}, headers)
            messages.extend(self._thread_messages(thread))
        return sorted(messages, key=lambda m: m.sent_at)
