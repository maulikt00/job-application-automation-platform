"""Shared fixtures for repository integration tests -- a fresh in-memory
SQLite database per test, exercised through the real engine/session
setup (create_engine_from_settings, session_scope), not a bare
:memory: connection, so PRAGMA foreign_keys and everything else in
session.py is actually in effect.
"""

from __future__ import annotations

import pytest

from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)


@pytest.fixture
def session_factory():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()
