"""Bangla, Banglish and mixed text is stored and returned exactly as received (CLAUDE.md rule 10).

The first test always runs on SQLite. The second runs only when TEST_DATABASE_URL points to a migrated
PostgreSQL database; it works inside a transaction that is rolled back, so nothing is left behind.
"""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models import Message, Project, User

BANGLA = "লগইন পেজে OTP লাগবে, ami chai report ta PDF e download hok 📄"
BANGLISH = "Apnara ki weekly report ta Friday er moddhe dite parben? খুব জরুরি।"
PROJECT_NAME = "ঢাকা ডেলিভারি অ্যাপ"
PROJECT_DESCRIPTION = "ক্লায়েন্ট: রহিম ট্রেডার্স — delivery tracking app"


def test_bangla_round_trip_through_api(client, make_user):
    _, headers = make_user()
    res = client.post("/projects", json={"name": PROJECT_NAME, "description": PROJECT_DESCRIPTION}, headers=headers)
    assert res.status_code == 201, res.text
    project = client.get(f"/projects/{res.json()['id']}", headers=headers).json()
    assert (project["name"], project["description"]) == (PROJECT_NAME, PROJECT_DESCRIPTION)

    base = f"/projects/{project['id']}"
    notes = f"Date: 2026-10-20\n\n{BANGLA}\n\n{BANGLISH}\n".encode("utf-8")
    upload = client.post(f"{base}/uploads", files=[("files", ("kickoff.md", notes, "text/markdown"))], headers=headers)
    assert upload.status_code == 200, upload.text

    texts = {m["text"] for m in client.get(f"{base}/messages", headers=headers).json()["items"]}
    assert texts == {BANGLA, BANGLISH}

    found = client.get(f"{base}/messages", params={"q": "লগইন পেজে"}, headers=headers).json()["items"]
    assert [m["text"] for m in found] == [BANGLA]


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set (PostgreSQL check)")
def test_bangla_round_trip_on_postgresql():
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            assert conn.dialect.name == "postgresql"
            trans = conn.begin()
            try:
                assert conn.scalar(text("SHOW server_encoding")) == "UTF8"
                db = Session(bind=conn)
                user = User(name="রহিম", email="unicode-check@example.com", password_hash="x")
                project = Project(name=PROJECT_NAME, description=PROJECT_DESCRIPTION, owner=user)
                message = Message(
                    source="whatsapp",
                    external_id="unicode-check-1",
                    channel="ক্লায়েন্ট গ্রুপ",
                    author="রহিম",
                    sent_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                    text=BANGLA,
                    raw={"line": BANGLA},
                )
                db.add_all([user, project])
                db.flush()
                message.project_id = project.id
                db.add(message)
                db.flush()

                row = conn.execute(
                    select(Message.text, Message.author, Message.channel, Message.raw, Message.sent_at).where(
                        Message.id == message.id
                    )
                ).one()
                assert row.text == BANGLA
                assert (row.author, row.channel) == ("রহিম", "ক্লায়েন্ট গ্রুপ")
                assert row.raw == {"line": BANGLA}
                assert row.sent_at == datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
                assert conn.scalar(select(Project.name).where(Project.id == project.id)) == PROJECT_NAME
                db.close()
            finally:
                trans.rollback()
    finally:
        engine.dispose()
