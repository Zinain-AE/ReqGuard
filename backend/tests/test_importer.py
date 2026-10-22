"""Storing normalised messages: things PostgreSQL rejects but SQLite accepts."""

from datetime import datetime, timezone

from app.connectors.base import NormalizedMessage
from app.connectors.importer import import_messages
from app.models import Message, Project, User


def test_nul_characters_are_removed_but_raw_is_kept(db_session_factory):
    db = db_session_factory()
    user = User(name="Owner", email="owner@example.com", password_hash="x")
    project = Project(name="Acme", owner=user)
    db.add_all([user, project])
    db.flush()

    msg = NormalizedMessage(
        source="email",
        external_id="m1",
        channel="Sub\x00ject",
        author="Ri\x00na",
        sent_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        text="Need\x00 export to PDF",
        raw={"body": "Need\x00 export to PDF"},
    )
    counts = import_messages(db, project.id, None, [msg])
    db.commit()

    assert counts.imported == 1
    stored = db.query(Message).one()
    assert (stored.channel, stored.author, stored.text) == ("Subject", "Rina", "Need export to PDF")
    assert stored.raw == {"body": "Need\x00 export to PDF"}
    db.close()
