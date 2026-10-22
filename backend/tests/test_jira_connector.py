"""Jira connector: ADF → text, issues + comments, pagination, errors. All HTTP is mocked."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.connectors.http import ConnectorError
from app.connectors.jira import JiraConnector, JiraSettings, adf_to_text
from tests.conftest import api_json

BASE = "https://acme-demo.atlassian.net"


def make_connector(key: str = "ACME") -> JiraConnector:
    return JiraConnector(JiraSettings(project_key=key), base_url=BASE + "/", email="me@x.com", api_token="tok")


def mock_project(router: respx.Router):
    search = router.get(f"{BASE}/rest/api/3/search/jql")
    search.side_effect = [
        httpx.Response(200, json=api_json("jira/search_page1.json")),
        httpx.Response(200, json=api_json("jira/search_page2.json")),
    ]
    router.get(f"{BASE}/rest/api/3/issue/ACME-1/comment").respond(json=api_json("jira/comments_ACME-1.json"))
    router.get(f"{BASE}/rest/api/3/issue/ACME-2/comment").respond(json=api_json("jira/comments_ACME-2.json"))
    return search


# ---------- ADF ----------


def test_adf_paragraphs_marks_and_lists():
    description = api_json("jira/search_page1.json")["issues"][0]["fields"]["description"]
    assert adf_to_text(description) == (
        "Users must be able to reset their password by email.\n\n"
        "- The link expires after 30 minutes\n"
        "- It should be fast"
    )


def test_adf_nested_ordered_list_heading_table_and_inline_nodes():
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Scope"}]},
            {
                "type": "orderedList",
                "attrs": {"order": 3},
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Login"}]},
                            {
                                "type": "bulletList",
                                "content": [
                                    {
                                        "type": "listItem",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "SSO"}]}],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {"type": "rule"},
            {"type": "mediaSingle", "content": [{"type": "media", "attrs": {"id": "x"}}]},
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Role"}]}]},
                            {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Limit"}]}]},
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Admin"}]}]},
                            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "10"}]}]},
                        ],
                    },
                ],
            },
            {
                "type": "panel",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "See "},
                            {"type": "inlineCard", "attrs": {"url": "https://example.com/spec"}},
                            {"type": "text", "text": " by "},
                            {"type": "date", "attrs": {"timestamp": "1792800000000"}},
                            {"type": "emoji", "attrs": {"shortName": ":smile:", "text": "😄"}},
                        ],
                    }
                ],
            },
        ],
    }
    assert adf_to_text(doc) == (
        "Scope\n\n"
        "3. Login\n"
        "  - SSO\n\n"
        "Role | Limit\n"
        "Admin | 10\n\n"
        "See https://example.com/spec by 2026-10-24😄"
    )


def test_adf_plain_string_and_empty_values():
    assert adf_to_text("  plain text  ") == "plain text"
    assert adf_to_text(None) == ""
    assert adf_to_text({"type": "doc", "content": []}) == ""


# ---------- Settings ----------


def test_project_key_is_normalised_and_checked():
    assert JiraSettings(project_key=" acme ").project_key == "ACME"
    with pytest.raises(ValueError):
        JiraSettings(project_key="ACME\" OR project = OTHER")


# ---------- Fetch ----------


@respx.mock
def test_fetch_issues_and_comments_with_pagination():
    search = mock_project(respx.mock)
    with make_connector() as connector:
        messages = connector.fetch()

    assert [m.external_id for m in messages] == ["issue:10001", "comment:20001", "comment:20002", "issue:10002"]
    issue = messages[0]
    assert issue.source == "jira"
    assert issue.channel == "ACME-1"
    assert issue.author == "Sarah Client"
    assert issue.sent_at == datetime(2026, 10, 20, 9, 15, tzinfo=timezone.utc)
    assert issue.text.startswith("Password reset by email\n\nUsers must be able to reset")
    assert issue.raw["key"] == "ACME-1"

    assert messages[1].text == "@Sarah Client should admins also get a reset link?"
    assert messages[1].author == "Tom Manager"
    assert messages[2].text == "Yes, admins too.\nThanks!"
    # Issue without a description: only the summary; +0600 offset converted to UTC
    assert messages[3].text == "Export monthly report"
    assert messages[3].sent_at == datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)

    first, second = (call.request for call in search.calls)
    assert first.url.params["jql"] == 'project = "ACME" ORDER BY created ASC'
    assert "nextPageToken" not in first.url.params
    assert second.url.params["nextPageToken"] == "page-2-token"
    assert first.headers["Authorization"].startswith("Basic ")


@respx.mock
def test_since_adds_updated_filter():
    search = mock_project(respx.mock)
    with make_connector() as connector:
        connector.fetch(since=datetime(2026, 10, 21, 12, 30, tzinfo=timezone.utc))
    jql = search.calls[0].request.url.params["jql"]
    assert jql == 'project = "ACME" AND updated >= "2026/10/20 12:30" ORDER BY created ASC'


@respx.mock
def test_comment_pagination():
    respx.get(f"{BASE}/rest/api/3/search/jql").respond(
        json={"issues": [api_json("jira/search_page1.json")["issues"][0]], "isLast": True}
    )
    page = api_json("jira/comments_ACME-1.json")
    comments = respx.get(f"{BASE}/rest/api/3/issue/ACME-1/comment")
    comments.side_effect = [
        httpx.Response(200, json={**page, "total": 2, "comments": page["comments"][:1]}),
        httpx.Response(200, json={**page, "startAt": 1, "total": 2, "comments": page["comments"][1:]}),
    ]
    with make_connector() as connector:
        messages = connector.fetch()
    assert len(messages) == 3
    assert comments.calls[1].request.url.params["startAt"] == "1"


@respx.mock
def test_wrong_token_gives_clear_error():
    respx.get(f"{BASE}/rest/api/3/search/jql").respond(401, json={"errorMessages": ["Unauthorized"]})
    with make_connector() as connector, pytest.raises(ConnectorError, match="JIRA_API_TOKEN"):
        connector.fetch()


@respx.mock
def test_unknown_project_gives_clear_error():
    respx.get(f"{BASE}/rest/api/3/search/jql").respond(
        400, json={"errorMessages": ["The value 'NOPE' does not exist for the field 'project'."]}
    )
    with make_connector("NOPE") as connector, pytest.raises(ConnectorError, match="HTTP 400"):
        connector.fetch()
