"""Telegram connector (Bot API getUpdates).

Imports text messages from groups, supergroups and channels the bot was added to. The bot's privacy
mode must be off (BotFather → /setprivacy → Disable) so it receives every group message.

How getUpdates works, and what that means here:
- Telegram keeps updates for about 24 hours only; sync at least once a day.
- Calling getUpdates with offset = last update_id + 1 confirms (deletes) all older updates, for every
  chat. The last update_id is stored in Source.config["state"] after the messages are saved.
  Updates for chats outside this source's chat filter are confirmed too and not imported anywhere,
  so use one Telegram source per bot.
- getUpdates does not work while a webhook is set for the bot.
"""

from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel

from app.connectors.base import NormalizedMessage
from app.connectors.http import MAX_PAGES, ApiConnector, ConnectorError, json_body, send

SOURCE = "telegram"
SERVICE = "Telegram"
AUTH_HINT = "Check TELEGRAM_BOT_TOKEN in backend/.env."
PAGE_SIZE = 100
GROUP_CHATS = {"group", "supergroup", "channel"}


class TelegramSettings(BaseModel):
    # Only import these chats; empty = every group the bot is in
    chat_ids: list[int] = []


def _author(message: dict) -> str:
    sender = message.get("from") or {}
    name = " ".join(p for p in (sender.get("first_name"), sender.get("last_name")) if p)
    if name:
        return name
    if sender.get("username"):
        return f"@{sender['username']}"
    # Channel posts have no sender, only the channel
    return str(message.get("author_signature") or (message.get("sender_chat") or {}).get("title") or "")


class TelegramConnector(ApiConnector):
    source = SOURCE
    label = "Telegram"
    required_env = ("TELEGRAM_BOT_TOKEN",)
    Settings = TelegramSettings

    def __init__(
        self,
        settings: TelegramSettings,
        *,
        token: str,
        client: httpx.Client | None = None,
        state: dict | None = None,
    ):
        super().__init__(client, state)
        self.settings = settings
        # The URL contains the token: it is never logged or put in an error message (see http.py)
        self.url = f"https://api.telegram.org/bot{token}/getUpdates"

    def _updates(self, offset: int | None) -> list[dict]:
        params: dict[str, Any] = {
            "limit": PAGE_SIZE,
            "timeout": 0,
            "allowed_updates": '["message","channel_post"]',
        }
        if offset is not None:
            params["offset"] = offset
        response = send(
            self.client, "GET", self.url, service=SERVICE, auth_hint=AUTH_HINT, params=params, allow_status=(404, 409)
        )
        if response.status_code == 404:
            # Telegram answers 404 when the token has a wrong format
            raise ConnectorError(f"Telegram rejected the bot token. {AUTH_HINT}")
        if response.status_code == 409:
            raise ConnectorError(
                "A webhook is set for this Telegram bot, so messages cannot be read with getUpdates. "
                "Remove it with deleteWebhook."
            )
        data = json_body(response, SERVICE)
        if not data.get("ok"):
            raise ConnectorError(f"Telegram API error: {data.get('description') or 'unknown error'}")
        return data.get("result") or []

    def _to_message(self, message: dict) -> NormalizedMessage | None:
        chat = message.get("chat") or {}
        if chat.get("type") not in GROUP_CHATS:
            return None
        if self.settings.chat_ids and chat.get("id") not in self.settings.chat_ids:
            return None
        text = str(message.get("text") or message.get("caption") or "").strip()
        if not text:
            return None
        return NormalizedMessage(
            source=SOURCE,
            external_id=f"{chat['id']}:{message['message_id']}",
            channel=str(chat.get("title") or chat["id"]),
            author=_author(message),
            sent_at=datetime.fromtimestamp(int(message["date"]), tz=timezone.utc),
            text=text,
            raw={"chat_id": chat["id"], "message": message},
        )

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        """`since` is not used: the stored update_id decides what is new."""
        last = self.state.get("last_update_id")
        messages: list[NormalizedMessage] = []
        for _ in range(MAX_PAGES):
            updates = self._updates(last + 1 if isinstance(last, int) else None)
            if not updates:
                break
            for update in updates:
                last = max(int(update["update_id"]), last if isinstance(last, int) else -1)
                message = update.get("message") or update.get("channel_post")
                if message:
                    normalized = self._to_message(message)
                    if normalized is not None:
                        messages.append(normalized)
            if len(updates) < PAGE_SIZE:
                break
        if isinstance(last, int):
            self.state["last_update_id"] = last
        return sorted(messages, key=lambda m: m.sent_at)
