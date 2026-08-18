"""Tests for SqliteAnswerRepository."""

from __future__ import annotations

import pytest

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import (
    Answer,
    Application,
    JobPosting,
    Profile,
    new_answer_id,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
)
from jaap.infrastructure.database.repositories.sqlite_answer_repository import (
    SqliteAnswerRepository,
)
from jaap.infrastructure.database.repositories.sqlite_application_repository import (
    SqliteApplicationRepository,
)
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.repositories.sqlite_profile_repository import (
    SqliteProfileRepository,
)


def _make_profile(session_factory) -> Profile:
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    SqliteProfileRepository(session_factory).save(profile)
    return profile


def test_save_then_get_round_trips_including_tags(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteAnswerRepository(session_factory)
    answer = Answer(
        id=new_answer_id(), profile_id=profile.id, question_key="why-us",
        answer_text="Because...", tags=["common"],
    )

    repo.save(answer)
    loaded = repo.get(answer.id)

    assert loaded == answer
    assert loaded.tags == ["common"]


def test_list_by_profile(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteAnswerRepository(session_factory)
    repo.save(Answer(id=new_answer_id(), profile_id=profile.id, question_key="q1", answer_text="a1", tags=[]))
    repo.save(Answer(id=new_answer_id(), profile_id=profile.id, question_key="q2", answer_text="a2", tags=[]))

    result = repo.list_by_profile(profile.id)

    assert sorted(a.question_key for a in result) == ["q1", "q2"]


def test_delete_referenced_answer_raises_referential_integrity_error(session_factory) -> None:
    profile = _make_profile(session_factory)
    answer_repo = SqliteAnswerRepository(session_factory)
    answer = Answer(id=new_answer_id(), profile_id=profile.id, question_key="why-us", answer_text="...", tags=[])
    answer_repo.save(answer)

    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    SqliteJobPostingRepository(session_factory).save(posting)

    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    application.answer_ids = (answer.id,)
    SqliteApplicationRepository(session_factory).save(application)

    with pytest.raises(ReferentialIntegrityError):
        answer_repo.delete(answer.id)
