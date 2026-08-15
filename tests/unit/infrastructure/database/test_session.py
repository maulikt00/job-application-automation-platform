"""Tests for engine creation and session_scope's transactional behavior."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.models import ProfileORM
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    session_scope,
)


def test_create_engine_creates_parent_directory_for_file_based_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "jaap.db"
    settings = Settings(_env_file=None, database_url=f"sqlite:///{db_path}")

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)

    assert db_path.parent.is_dir()
    assert db_path.exists()
    engine.dispose()


def test_create_engine_does_not_require_a_directory_for_in_memory_sqlite() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")

    # Must not raise -- there is no parent directory to create for :memory:.
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    engine.dispose()


def test_foreign_keys_are_enforced_on_sqlite_connections() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)

    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA foreign_keys")).scalar()
        assert result == 1
    engine.dispose()


def test_session_scope_commits_on_success() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    profile_id = uuid.uuid4()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))

    with session_scope(session_factory) as session:
        assert session.get(ProfileORM, profile_id) is not None
    engine.dispose()


def test_session_scope_rolls_back_on_exception() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    profile_id = uuid.uuid4()

    with pytest.raises(RuntimeError), session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        raise RuntimeError("simulated failure mid-transaction")

    with session_scope(session_factory) as session:
        # The add() above must not have been committed.
        assert session.get(ProfileORM, profile_id) is None
    engine.dispose()


def test_session_scope_rolls_back_on_integrity_error() -> None:
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    profile_id = uuid.uuid4()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        # Same primary key -- must fail and roll back cleanly.
        session.add(ProfileORM(id=profile_id, full_name="B", email="b@example.com"))
    engine.dispose()
