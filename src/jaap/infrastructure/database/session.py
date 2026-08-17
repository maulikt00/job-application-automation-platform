"""Database engine and session management.

Two small helpers are provided rather than a global engine/session: the
caller (eventually the composition root, Milestone 6+) constructs an
engine from Settings, builds a session factory from that engine, and uses
`session_scope()` to get a transactional session per unit of work. Nothing
here is a module-level singleton -- consistent with how Settings itself is
handled (see infrastructure/config/settings.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from jaap.infrastructure.config.settings import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create a SQLAlchemy Engine from Settings.database_url.

    For file-based SQLite URLs, ensures the parent directory exists
    (mirroring how logging_config.py handles settings.log_dir) so a fresh
    checkout doesn't fail with "unable to open database file" just because
    `data/` hasn't been created yet. In-memory SQLite URLs are left alone.
    """
    url = make_url(settings.database_url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, future=True)

    if url.drivername.startswith("sqlite"):
        # SQLite ignores foreign key constraints by default unless this
        # pragma is set on every connection -- without it, ON DELETE
        # CASCADE/SET NULL in models.py would silently do nothing.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope: commits on success, rolls back and
    re-raises on any exception, and always closes the session.

    Usage:
        with session_scope(session_factory) as session:
            session.add(some_orm_object)
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
