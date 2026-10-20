"""The Alembic migrations run forwards and backwards on SQLite."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_upgrade_and_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)  # alembic/env.py reads this
    config = Config(str(BACKEND_DIR / "alembic.ini"))

    command.upgrade(config, "head")
    engine = create_engine(url)
    assert {"users", "projects", "team_members", "sources", "messages"} <= set(inspect(engine).get_table_names())
    checks = inspect(engine).get_check_constraints("team_members")
    assert any(c["name"] == "ck_team_members_role" for c in checks)

    # Deleting a project removes its sources and messages in the database itself
    def on_delete(table: str, referred: str) -> str | None:
        fks = inspect(engine).get_foreign_keys(table)
        return next(fk["options"].get("ondelete") for fk in fks if fk["referred_table"] == referred)

    assert on_delete("sources", "projects") == "CASCADE"
    assert on_delete("messages", "projects") == "CASCADE"
    assert on_delete("team_members", "projects") == "CASCADE"

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
