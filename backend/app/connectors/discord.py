"""Discord connector (REST API v10, bot token).

Lists the text channels of one server (guild) and reads their messages forward with `after=<id>`.
The newest message id per channel is stored in Source.config["state"], so the next sync only reads
new messages. The bot needs the "Message Content" intent, and View Channel + Read Message History
permissions in the channels.
"""

import re
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, field_validator

from app.connectors.base import NormalizedMessage, as_utc
from app.connectors.http import MAX_PAGES, ApiConnector, ConnectorError, json_body, send

SOURCE = "discord"
SERVICE = "Discord"
API = "https://discord.com/api/v10"
AUTH_HINT = (
    "Check DISCORD_BOT_TOKEN in backend/.env and that the bot can view the channel and read message history."
)
PAGE_SIZE = 100
TEXT_CHANNEL_TYPES = {0, 5}  # GUILD_TEXT, GUILD_ANNOUNCEMENT
MESSAGE_TYPES = {0, 19}  # DEFAULT, REPLY (joins, pins, boosts... are skipped)


class DiscordSettings(BaseModel):
    guild_id: str
    # Channel names (with or without #) or ids; empty = every text channel the bot can read
    channels: list[str] = []

    @field_validator("guild_id")
    @classmethod
    def check_guild(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"\d{15,21}", value):
            raise ValueError("Server (guild) id is a long number; copy it with Developer Mode → Copy Server ID")
        return value

    @field_validator("channels")
    @classmethod
    def clean(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(c.strip().lstrip("#").strip() for c in value if c.strip().lstrip("#").strip()))


def _author(message: dict) -> str:
    author = message.get("author") or {}
    return str(author.get("global_name") or author.get("username") or author.get("id") or "")


class DiscordConnector(ApiConnector):
    source = SOURCE
    label = "Discord"
    required_env = ("DISCORD_BOT_TOKEN",)
    Settings = DiscordSettings

    def __init__(
        self,
        settings: DiscordSettings,
        *,
        token: str,
        client: httpx.Client | None = None,
        state: dict | None = None,
    ):
        super().__init__(client, state)
        self.settings = settings
        self.headers = {
            "Authorization": f"Bot {token}",
            # Discord asks bots to identify themselves this way
            "User-Agent": "DiscordBot (https://github.com/reqguard, 0.1)",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = send(
            self.client, "GET", f"{API}{path}", service=SERVICE, auth_hint=AUTH_HINT, params=params,
            headers=self.headers,
        )
        return json_body(response, SERVICE)

    def _selected_channels(self) -> list[dict]:
        channels = [
            c for c in self._get(f"/guilds/{self.settings.guild_id}/channels") if c.get("type") in TEXT_CHANNEL_TYPES
        ]
        if not self.settings.channels:
            return channels
        by_key = {c["id"]: c for c in channels} | {c.get("name", ""): c for c in channels}
        missing = [name for name in self.settings.channels if name not in by_key]
        if missing:
            raise ConnectorError(f"Discord channel(s) not found: {', '.join('#' + m for m in missing)}.")
        return [by_key[name] for name in self.settings.channels]

    def _channel_messages(self, channel_id: str, after: str) -> list[dict]:
        found: list[dict] = []
        for _ in range(MAX_PAGES):
            page = self._get(f"/channels/{channel_id}/messages", {"limit": PAGE_SIZE, "after": after})
            if not page:
                break
            found.extend(page)
            # Order inside a page is not guaranteed to be oldest first; snowflake ids grow with time
            after = str(max(int(m["id"]) for m in page))
            if len(page) < PAGE_SIZE:
                break
        return found

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        """`since` is not used: the stored message id per channel decides what is new."""
        last_ids: dict[str, str] = dict(self.state.get("last_message_ids") or {})
        messages: list[NormalizedMessage] = []
        human_messages = 0
        for channel in self._selected_channels():
            channel_id = str(channel["id"])
            raw_messages = self._channel_messages(channel_id, last_ids.get(channel_id, "0"))
            if raw_messages:
                last_ids[channel_id] = str(max(int(m["id"]) for m in raw_messages))
            for message in raw_messages:
                if message.get("type") not in MESSAGE_TYPES or (message.get("author") or {}).get("bot"):
                    continue
                human_messages += 1
                text = str(message.get("content") or "").strip()
                if not text:
                    continue
                messages.append(
                    NormalizedMessage(
                        source=SOURCE,
                        external_id=str(message["id"]),
                        channel=f"#{channel.get('name', channel_id)}",
                        author=_author(message),
                        sent_at=as_utc(datetime.fromisoformat(message["timestamp"])),
                        text=text,
                        raw={"guild_id": self.settings.guild_id, "channel_id": channel_id, "message": message},
                    )
                )
        if human_messages and not messages:
            raise ConnectorError(
                "Discord returned messages without text. Turn on the Message Content intent for the bot "
                "(Developer Portal → Bot → Privileged Gateway Intents)."
            )
        self.state["last_message_ids"] = last_ids
        return sorted(messages, key=lambda m: m.sent_at)
