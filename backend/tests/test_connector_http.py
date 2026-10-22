"""The shared HTTP helper of the API connectors: 429 retries and clear error messages."""

import httpx
import pytest
import respx

from app.connectors import http
from app.connectors.http import ConnectorError, send

URL = "https://api.example.com/items"


@pytest.fixture
def waits(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(http, "sleep", calls.append)
    return calls


@respx.mock
def test_retries_after_429_using_header(waits):
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, json={"ok": True})]
    )
    with httpx.Client() as client:
        res = send(client, "GET", URL, service="Example")
    assert res.json() == {"ok": True}
    assert route.call_count == 2
    assert waits == [2.0]


@respx.mock
def test_retry_after_from_json_body(waits):
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, json={"retry_after": 0.5}),  # Discord
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 3}}),  # Telegram
            httpx.Response(200, json=[]),
        ]
    )
    with httpx.Client() as client:
        send(client, "GET", URL, service="Example")
    assert waits == [0.5, 3.0]


@respx.mock
def test_gives_up_after_max_retries(waits):
    respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
    with httpx.Client() as client, pytest.raises(ConnectorError, match="rate limit"):
        send(client, "GET", URL, service="Example")
    assert len(waits) == http.MAX_RETRIES


@respx.mock
def test_does_not_wait_too_long(waits):
    respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "3600"}))
    with httpx.Client() as client, pytest.raises(ConnectorError, match="rate limit"):
        send(client, "GET", URL, service="Example")
    assert waits == []


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "rejected the credentials"), (403, "denied access"), (404, "could not find"), (500, "HTTP 500")],
)
@respx.mock
def test_error_status_messages(status, message):
    respx.get(URL).mock(return_value=httpx.Response(status))
    with httpx.Client() as client, pytest.raises(ConnectorError, match=message) as exc:
        send(client, "GET", URL, service="Example", auth_hint="Check EXAMPLE_TOKEN.")
    assert str(exc.value).startswith("Example ")


@respx.mock
def test_network_error_message_hides_url():
    secret_url = "https://api.telegram.org/bot123:SECRET/getUpdates"
    respx.get(secret_url).mock(side_effect=httpx.ConnectError("boom"))
    with httpx.Client() as client, pytest.raises(ConnectorError) as exc:
        send(client, "GET", secret_url, service="Telegram")
    assert "SECRET" not in str(exc.value)
