"""Tests for ORM model relationships, cascade delete behavior, and the
JobPosting deduplication index -- exercised against a real in-memory
SQLite database via create_engine_from_settings/session_scope, so
foreign-key enforcement and SQLite-specific behavior (the partial unique
index) are actually tested, not assumed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.models import (
    AnswerORM,
    ApplicationAnswerORM,
    ApplicationORM,
    ApplicationStatusEventORM,
    CoverLetterTemplateORM,
    JobPostingORM,
    ProfileORM,
    ResumeORM,
)
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    session_scope,
)


@pytest.fixture
def session_factory():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_application_relationships_load_correctly(session_factory) -> None:
    profile_id, resume_id, posting_id, app_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="Maulik Patel", email="m@example.com"))
        session.add(
            ResumeORM(
                id=resume_id, profile_id=profile_id, label="Backend", file_path="r.pdf", uploaded_at=now
            )
        )
        session.add(
            JobPostingORM(
                id=posting_id,
                company_name="Acme",
                title="Engineer",
                url="https://acme.example.com/1",
                platform="greenhouse",
            )
        )
        app = ApplicationORM(
            id=app_id,
            profile_id=profile_id,
            job_posting_id=posting_id,
            resume_id=resume_id,
            current_status="draft",
            created_at=now,
        )
        app.status_events.append(ApplicationStatusEventORM(sequence=0, status="draft", changed_at=now))
        session.add(app)

    with session_scope(session_factory) as session:
        loaded = session.get(ApplicationORM, app_id)
        assert loaded is not None
        assert loaded.profile.full_name == "Maulik Patel"
        assert loaded.resume.label == "Backend"
        assert loaded.job_posting.company_name == "Acme"
        assert [e.status for e in loaded.status_events] == ["draft"]


def test_status_events_preserve_insertion_order_via_sequence(session_factory) -> None:
    profile_id, posting_id, app_id = (uuid.uuid4() for _ in range(3))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="submitted", created_at=now
        )
        app.status_events.append(ApplicationStatusEventORM(sequence=0, status="draft", changed_at=now))
        app.status_events.append(ApplicationStatusEventORM(sequence=1, status="submitted", changed_at=now))
        session.add(app)

    with session_scope(session_factory) as session:
        loaded = session.get(ApplicationORM, app_id)
        assert [e.status for e in loaded.status_events] == ["draft", "submitted"]


def test_application_answer_associations_are_created_and_loaded(session_factory) -> None:
    profile_id, posting_id, app_id, answer_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            AnswerORM(id=answer_id, profile_id=profile_id, question_key="why-us", answer_text="...", tags=[])
        )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="draft", created_at=now
        )
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_id, position=0))
        session.add(app)

    with session_scope(session_factory) as session:
        loaded = session.get(ApplicationORM, app_id)
        assert [a.answer.question_key for a in loaded.answer_associations] == ["why-us"]


def test_answer_associations_preserve_position_order_regardless_of_insertion_order(
    session_factory,
) -> None:
    profile_id, posting_id, app_id = (uuid.uuid4() for _ in range(3))
    answer_ids = [uuid.uuid4() for _ in range(3)]
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        for i, answer_id in enumerate(answer_ids):
            session.add(
                AnswerORM(
                    id=answer_id, profile_id=profile_id, question_key=f"q{i}", answer_text=f"a{i}", tags=[]
                )
            )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="draft", created_at=now
        )
        # Deliberately scrambled insertion order -- position, not
        # insertion order, must determine the reloaded order.
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_ids[2], position=2))
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_ids[0], position=0))
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_ids[1], position=1))
        session.add(app)

    with session_scope(session_factory) as session:
        loaded = session.get(ApplicationORM, app_id)
        assert [a.answer_id for a in loaded.answer_associations] == answer_ids


def test_deleting_an_answer_referenced_by_an_application_is_rejected(session_factory) -> None:
    profile_id, posting_id, app_id, answer_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            AnswerORM(id=answer_id, profile_id=profile_id, question_key="why-us", answer_text="...", tags=[])
        )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="draft", created_at=now
        )
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_id, position=0))
        session.add(app)

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        session.delete(session.get(AnswerORM, answer_id))


def test_deleting_a_resume_referenced_by_an_application_is_rejected(session_factory) -> None:
    profile_id, resume_id, posting_id, app_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            ResumeORM(id=resume_id, profile_id=profile_id, label="R", file_path="r.pdf", uploaded_at=now)
        )
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            ApplicationORM(
                id=app_id, profile_id=profile_id, job_posting_id=posting_id, resume_id=resume_id,
                current_status="draft", created_at=now,
            )
        )

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        session.delete(session.get(ResumeORM, resume_id))


def test_deleting_a_cover_letter_template_referenced_by_an_application_is_rejected(
    session_factory,
) -> None:
    profile_id, template_id, posting_id, app_id = (uuid.uuid4() for _ in range(4))

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            CoverLetterTemplateORM(
                id=template_id, profile_id=profile_id, name="Standard", body_template="Dear team, ..."
            )
        )
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            ApplicationORM(
                id=app_id, profile_id=profile_id, job_posting_id=posting_id,
                cover_letter_template_id=template_id, current_status="draft", created_at=_now(),
            )
        )

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        session.delete(session.get(CoverLetterTemplateORM, template_id))


def test_status_events_and_answer_associations_are_accessible_after_session_close(
    session_factory,
) -> None:
    # Regression test for the DetachedInstanceError risk identified in the
    # Milestone 4 review (ADR-0004): these two relationships are
    # eager-loaded (lazy="selectin") specifically so this works.
    profile_id, posting_id, app_id, answer_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            AnswerORM(id=answer_id, profile_id=profile_id, question_key="why-us", answer_text="...", tags=[])
        )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="draft", created_at=now
        )
        app.status_events.append(ApplicationStatusEventORM(sequence=0, status="draft", changed_at=now))
        app.answer_associations.append(ApplicationAnswerORM(answer_id=answer_id, position=0))
        session.add(app)

    with session_scope(session_factory) as session:
        loaded = session.get(ApplicationORM, app_id)

    # `loaded`'s session has closed at this point -- accessing these
    # relationships must not raise DetachedInstanceError.
    assert [e.status for e in loaded.status_events] == ["draft"]
    assert [a.answer_id for a in loaded.answer_associations] == [answer_id]


def test_deleting_profile_cascades_to_owned_aggregates(session_factory) -> None:
    profile_id, resume_id, posting_id, app_id = (uuid.uuid4() for _ in range(4))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            ResumeORM(id=resume_id, profile_id=profile_id, label="R", file_path="r.pdf", uploaded_at=now)
        )
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        session.add(
            ApplicationORM(
                id=app_id, profile_id=profile_id, job_posting_id=posting_id, resume_id=resume_id,
                current_status="draft", created_at=now,
            )
        )

    with session_scope(session_factory) as session:
        session.delete(session.get(ProfileORM, profile_id))

    with session_scope(session_factory) as session:
        assert session.get(ProfileORM, profile_id) is None
        assert session.get(ResumeORM, resume_id) is None
        assert session.get(ApplicationORM, app_id) is None
        # JobPosting is not owned by Profile (per the domain-model diagram)
        # and must survive the cascade.
        assert session.get(JobPostingORM, posting_id) is not None


def test_deleting_application_cascades_to_its_status_events(session_factory) -> None:
    profile_id, posting_id, app_id = (uuid.uuid4() for _ in range(3))
    now = _now()

    with session_scope(session_factory) as session:
        session.add(ProfileORM(id=profile_id, full_name="A", email="a@example.com"))
        session.add(
            JobPostingORM(id=posting_id, company_name="Acme", title="Eng", url="https://acme.example.com/1")
        )
        app = ApplicationORM(
            id=app_id, profile_id=profile_id, job_posting_id=posting_id, current_status="draft", created_at=now
        )
        app.status_events.append(ApplicationStatusEventORM(sequence=0, status="draft", changed_at=now))
        session.add(app)

    with session_scope(session_factory) as session:
        session.delete(session.get(ApplicationORM, app_id))

    with session_scope(session_factory) as session:
        remaining = (
            session.query(ApplicationStatusEventORM).filter_by(application_id=app_id).count()
        )
        assert remaining == 0


def test_duplicate_platform_and_external_id_is_rejected(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.add(
            JobPostingORM(
                id=uuid.uuid4(), company_name="A", title="X",
                url="https://a.example.com/1", platform="greenhouse", external_id="dup-1",
            )
        )

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        session.add(
            JobPostingORM(
                id=uuid.uuid4(), company_name="B", title="Y",
                url="https://a.example.com/2", platform="greenhouse", external_id="dup-1",
            )
        )


def test_multiple_null_external_ids_are_allowed(session_factory) -> None:
    # The unique index is partial (WHERE external_id IS NOT NULL), so
    # postings without one (e.g. manually entered) must not collide.
    with session_scope(session_factory) as session:
        session.add(
            JobPostingORM(id=uuid.uuid4(), company_name="A", title="X", url="https://a.example.com/1")
        )
        session.add(
            JobPostingORM(id=uuid.uuid4(), company_name="B", title="Y", url="https://a.example.com/2")
        )
    # No exception -- both rows with external_id=None coexist.


def test_same_external_id_on_different_platforms_is_allowed(session_factory) -> None:
    # The unique index is on the (platform, external_id) pair, not
    # external_id alone -- different platforms may reuse the same ID shape.
    with session_scope(session_factory) as session:
        session.add(
            JobPostingORM(
                id=uuid.uuid4(), company_name="A", title="X",
                url="https://a.example.com/1", platform="greenhouse", external_id="123",
            )
        )
        session.add(
            JobPostingORM(
                id=uuid.uuid4(), company_name="B", title="Y",
                url="https://b.example.com/1", platform="lever", external_id="123",
            )
        )
    # No exception -- different platforms, same external_id string.
