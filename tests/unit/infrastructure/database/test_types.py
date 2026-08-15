"""Tests for UTCDateTime: timezone-aware round-tripping and rejection of
naive datetimes, using a real in-memory SQLite database rather than
testing the TypeDecorator's methods in isolation, since the behavior that
matters is how it behaves through an actual bind/result cycle.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from jaap.infrastructure.database import (
    models,  # noqa: F401  (registers ORM tables on Base)
)
from jaap.infrastructure.database.base import Base


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_timezone_aware_datetime_round_trips_as_utc(engine) -> None:
    import uuid

    from jaap.infrastructure.database.models import ProfileORM

    original = datetime(2026, 3, 1, 12, 30, tzinfo=timezone(timedelta(hours=5)))
    profile_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.commit()

    # updated_at is set by the ORM default, not directly controllable here,
    # so round-trip a value we DO control: use a Resume's uploaded_at.
    from jaap.infrastructure.database.models import ResumeORM

    resume_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            ResumeORM(
                id=resume_id,
                profile_id=profile_id,
                label="Backend",
                file_path="r.pdf",
                uploaded_at=original,
            )
        )
        session.commit()

    with Session(engine) as session:
        loaded = session.get(ResumeORM, resume_id)
        assert loaded is not None
        assert loaded.uploaded_at.tzinfo == timezone.utc
        assert loaded.uploaded_at == original  # equal instants, despite differing offsets


def test_naive_datetime_is_rejected(engine) -> None:
    import uuid

    from jaap.infrastructure.database.models import ProfileORM, ResumeORM

    profile_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.commit()

    with Session(engine) as session:
        session.add(
            ResumeORM(
                id=uuid.uuid4(),
                profile_id=profile_id,
                label="Backend",
                file_path="r.pdf",
                uploaded_at=datetime.now(),  # noqa: DTZ005 -- deliberately naive, testing rejection
            )
        )
        with pytest.raises(StatementError):
            session.commit()
