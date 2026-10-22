"""Shared pieces of the API connectors (Jira, Slack, Gmail, Telegram, Discord).

- `ApiConnector`: base class. Credentials are passed in by the caller (read from .env or decrypted
  from the database); a connector never stores them anywhere.
- `send()`: one HTTP request with retries on HTTP 429 (rate limit) and clear error messages.
  Error messages never contain the URL, because the Telegram URL contains the bot token.
"""

import logging
import time
from datetime import datetime
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel

from app.connectors.base import Connector, NormalizedMessage

# httpx logs every request URL at INFO level; Telegram URLs contain the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT = httpx.Timeout(30.0)
MAX_RETRIES = 3
# Longer waits are not worth blocking a sync request for; the user can sync again later
MAX_WAIT_SECONDS = 60.0
# Safety limit for every paginated loop
MAX_PAGES = 200

# Replaced in tests so retries do not wait
sleep = time.sleep


class ConnectorError(Exception):
    """A problem the user can understand and fix (wrong token, missing channel, rate limit...)."""


class NotConfiguredError(ConnectorError):
    """Required settings are missing from backend/.env."""


class NeedsAuthError(ConnectorError):
    """The account has to be connected (again), e.g. Gmail OAuth."""


class ApiConnector(Connector):
    """A connector that calls an external API. Subclasses set the class attributes below."""

    source: ClassVar[str]
    label: ClassVar[str]
    # Names of the .env variables this connector needs (shown to the user when missing, never the values)
    required_env: ClassVar[tuple[str, ...]]
    # User-entered, non-secret settings stored in Source.config["settings"]
    Settings: ClassVar[type[BaseModel]]

    def __init__(self, client: httpx.Client | None = None, state: dict[str, Any] | None = None):
        self._own_client = client is None
        self.client = client or httpx.Client(timeout=TIMEOUT)
        # Sync cursor (e.g. Telegram's last update_id). Saved by the caller after the messages are stored.
        self.state: dict[str, Any] = dict(state or {})

    def close(self) -> None:
        if self._own_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        raise NotImplementedError


def _retry_after(response: httpx.Response) -> float:
    """Seconds to wait, from the Retry-After header or the JSON body (Discord, Telegram)."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for value in (body.get("retry_after"), (body.get("parameters") or {}).get("retry_after")):
            if isinstance(value, (int, float)):
                return float(value)
    return 1.0


def send(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    service: str,
    auth_hint: str = "",
    allow_status: tuple[int, ...] = (),
    **kwargs: Any,
) -> httpx.Response:
    """Send a request; retry on 429; raise ConnectorError for every other error status.

    Statuses in `allow_status` are returned to the caller, which reads the error body itself.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TimeoutException:
            raise ConnectorError(f"{service} did not answer in time. Try again later.") from None
        except httpx.HTTPError:
            raise ConnectorError(f"Could not reach {service}. Check the internet connection and settings.") from None

        if response.status_code != 429:
            break
        wait = _retry_after(response)
        if attempt == MAX_RETRIES or wait > MAX_WAIT_SECONDS:
            raise ConnectorError(f"{service} rate limit reached. Try again in a few minutes.")
        sleep(wait)

    status = response.status_code
    if status in allow_status:
        return response
    hint = f" {auth_hint}" if auth_hint else ""
    if status == 401:
        raise ConnectorError(f"{service} rejected the credentials (HTTP 401).{hint}")
    if status == 403:
        raise ConnectorError(f"{service} denied access (HTTP 403). Check the permissions of the token.{hint}")
    if status == 404:
        raise ConnectorError(f"{service} could not find the requested item (HTTP 404). Check the source settings.")
    if status >= 400:
        raise ConnectorError(f"{service} returned an error (HTTP {status}).")
    return response


def json_body(response: httpx.Response, service: str) -> Any:
    try:
        return response.json()
    except ValueError:
        raise ConnectorError(f"{service} returned a response that is not JSON.") from None
