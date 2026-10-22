"""Slack connector (Web API, bot token with scopes channels:read and channels:history).

For each selected public channel: conversations.history (cursor pagination), and
conversations.replies for messages that started a thread. The bot must be a member of the channel.
Limitation: with `since`, replies added later to an older thread are not picked up.
"""

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, field_validator

from app.connectors.base import NormalizedMessage
from app.connectors.http import MAX_PAGES, ApiConnector, ConnectorError, json_body, send

SOURCE = "slack"
SERVICE = "Slack"
API = "https://slack.com/api"
AUTH_HINT = "Check SLACK_BOT_TOKEN in backend/.env."
PAGE_SIZE = 200
SINCE_MARGIN = timedelta(minutes=5)

# Message subtypes that carry what a person wrote; all others (joins, topic changes, bots...) are skipped
KEEP_SUBTYPES = {None, "thread_broadcast", "file_share", "me_message"}

_ERRORS = {
    "invalid_auth": f"Slack rejected the bot token. {AUTH_HINT}",
    "not_authed": f"Slack rejected the bot token. {AUTH_HINT}",
    "account_inactive": f"The Slack bot token is no longer active. {AUTH_HINT}",
    "token_revoked": f"The Slack bot token was revoked. {AUTH_HINT}",
    "missing_scope": "The Slack bot needs the scopes channels:read and channels:history.",
    "channel_not_found": "A selected Slack channel was not found.",
}

_USER_RE = re.compile(r"<@([A-Z0-9]+)(?:\|([^>]+))?>")
_CHANNEL_RE = re.compile(r"<#([A-Z0-9]+)(?:\|([^>]*))?>")
_SPECIAL_RE = re.compile(r"<!(here|channel|everyone)(?:\|[^>]*)?>")
_LINK_RE = re.compile(r"<((?:https?|mailto):[^|>]+)(?:\|([^>]+))?>")


def slack_to_text(value: str) -> str:
    """Slack's markup to plain text: <@U1> → @U1, <#C1|general> → #general, <url|label> → label."""
    value = _USER_RE.sub(lambda m: f"@{m.group(2) or m.group(1)}", value)
    value = _CHANNEL_RE.sub(lambda m: f"#{m.group(2) or m.group(1)}", value)
    value = _SPECIAL_RE.sub(lambda m: f"@{m.group(1)}", value)
    value = _LINK_RE.sub(lambda m: m.group(2) or m.group(1).removeprefix("mailto:"), value)
    return html.unescape(value).strip()


class SlackSettings(BaseModel):
    # Channel names (with or without #) or channel ids
    channels: list[str]

    @field_validator("channels")
    @classmethod
    def clean(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(c.strip().lstrip("#").strip() for c in value if c.strip().lstrip("#").strip()))
        if not cleaned:
            raise ValueError("Choose at least one Slack channel")
        return cleaned


def _author(message: dict) -> str:
    profile = message.get("user_profile") or {}
    return str(profile.get("real_name") or profile.get("display_name") or message.get("user") or "")


class SlackConnector(ApiConnector):
    source = SOURCE
    label = "Slack"
    required_env = ("SLACK_BOT_TOKEN",)
    Settings = SlackSettings

    def __init__(
        self,
        settings: SlackSettings,
        *,
        token: str,
        client: httpx.Client | None = None,
        state: dict | None = None,
    ):
        super().__init__(client, state)
        self.settings = settings
        self.headers = {"Authorization": f"Bearer {token}"}

    def _call(self, method: str, params: dict[str, Any], channel_name: str = "") -> dict:
        response = send(
            self.client, "GET", f"{API}/{method}", service=SERVICE, auth_hint=AUTH_HINT, params=params,
            headers=self.headers,
        )
        data = json_body(response, SERVICE)
        if not data.get("ok"):
            error = str(data.get("error") or "unknown_error")
            if error == "not_in_channel":
                raise ConnectorError(
                    f"The Slack bot is not a member of #{channel_name}. Invite it in Slack with /invite @<bot name>."
                )
            raise ConnectorError(_ERRORS.get(error, f"Slack API error: {error}"))
        return data

    def _paged(self, method: str, params: dict[str, Any], key: str, channel_name: str = "") -> list[dict]:
        items: list[dict] = []
        params = {**params, "limit": PAGE_SIZE}
        for _ in range(MAX_PAGES):
            data = self._call(method, params, channel_name)
            items.extend(data.get(key) or [])
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
        return items

    def _selected_channels(self) -> list[dict]:
        channels = self._paged(
            "conversations.list", {"types": "public_channel", "exclude_archived": "true"}, "channels"
        )
        by_key = {c["id"]: c for c in channels} | {c.get("name", ""): c for c in channels}
        missing = [name for name in self.settings.channels if name not in by_key]
        if missing:
            raise ConnectorError(
                f"Slack channel(s) not found: {', '.join('#' + m for m in missing)}. "
                "Check the name; only public channels are supported."
            )
        return [by_key[name] for name in self.settings.channels]

    def _to_message(self, message: dict, channel: dict) -> NormalizedMessage | None:
        if message.get("subtype") not in KEEP_SUBTYPES or message.get("bot_id"):
            return None
        text = slack_to_text(str(message.get("text") or ""))
        ts = message.get("ts")
        if not text or not ts:
            return None
        return NormalizedMessage(
            source=SOURCE,
            external_id=f"{channel['id']}:{ts}",
            channel=f"#{channel.get('name', channel['id'])}",
            author=_author(message),
            sent_at=datetime.fromtimestamp(float(ts), tz=timezone.utc),
            text=text,
            raw={"channel_id": channel["id"], "message": message},
        )

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        messages: list[NormalizedMessage] = []
        for channel in self._selected_channels():
            name = channel.get("name", channel["id"])
            params: dict[str, Any] = {"channel": channel["id"]}
            if since is not None:
                params["oldest"] = f"{(since - SINCE_MARGIN).timestamp():.6f}"
            for message in self._paged("conversations.history", params, "messages", name):
                found = [message]
                if message.get("reply_count") and message.get("thread_ts") == message.get("ts"):
                    replies = self._paged(
                        "conversations.replies", {"channel": channel["id"], "ts": message["ts"]}, "messages", name
                    )
                    # The first item of conversations.replies is the parent message itself
                    found.extend(r for r in replies if r.get("ts") != message["ts"])
                for item in found:
                    normalized = self._to_message(item, channel)
                    if normalized is not None:
                        messages.append(normalized)
        return sorted(messages, key=lambda m: m.sent_at)
