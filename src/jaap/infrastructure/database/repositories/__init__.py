"""Concrete repository implementations (SqliteProfileRepository, etc.)
that satisfy the Protocol interfaces defined in
application/interfaces/repositories.py.

Each repository's constructor takes a `sessionmaker[Session]` (see
infrastructure/database/session.py's create_session_factory()), and
every method opens its own session_scope(), does its work, and returns
a fully-built domain object before that `with` block closes -- never a
raw ORM object. This directly follows the eager-loading/session-lifecycle
rule from ADR-0004: all ORM attribute/relationship access happens while
the session is open.
"""
