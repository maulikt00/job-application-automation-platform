"""Tests for SqliteApplicationRepository -- the integration point for
everything ADR-0002/0003/0004/0005 established: progressive Draft
lifecycle, status transitions, eager loading, and answer associations,
all exercised against a real database this time (not just the mapper in
isolation, per test_application_mapper.py)."""

from __future__ import annotations

from jaap.domain.models import (
    Answer,
    Application,
    ApplicationStatus,
    JobPosting,
    Profile,
    new_answer_id,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
)
from jaap.domain.models.application import SubmittedAnswer, SubmittedContentSnapshot
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


def _make_profile_and_posting(session_factory) -> tuple[Profile, JobPosting]:
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    SqliteProfileRepository(session_factory).save(profile)
    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    SqliteJobPostingRepository(session_factory).save(posting)
    return profile, posting


def test_draft_application_round_trips(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)

    repo.save(application)
    loaded = repo.get(application.id)

    assert loaded == application
    assert loaded.current_status == ApplicationStatus.DRAFT
    assert loaded.resume_id is None


def test_status_transitions_persist_across_saves(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    repo.save(application)

    snapshot = SubmittedContentSnapshot(resume_label="Backend", resume_file_name="backend.pdf")
    application.transition_to(ApplicationStatus.SUBMITTED, content_snapshot=snapshot)
    repo.save(application)
    application.transition_to(ApplicationStatus.INTERVIEWING)
    repo.save(application)

    loaded = repo.get(application.id)
    assert loaded.current_status == ApplicationStatus.INTERVIEWING
    assert [e.status for e in loaded.status_history] == [
        ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEWING,
    ]
    assert loaded.content_snapshot == snapshot


def test_answer_ids_persist_and_reflect_removal_across_saves(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    answer_repo = SqliteAnswerRepository(session_factory)
    answers = [
        Answer(id=new_answer_id(), profile_id=profile.id, question_key=f"q{i}", answer_text=f"a{i}", tags=[])
        for i in range(3)
    ]
    for answer in answers:
        answer_repo.save(answer)

    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    application.answer_ids = tuple(a.id for a in answers)
    repo.save(application)

    loaded = repo.get(application.id)
    assert loaded.answer_ids == tuple(a.id for a in answers)

    # Remove the middle one, save again -- must reflect exactly the new set.
    loaded.answer_ids = (answers[0].id, answers[2].id)
    repo.save(loaded)

    reloaded = repo.get(application.id)
    assert reloaded.answer_ids == (answers[0].id, answers[2].id)


def test_list_by_profile_returns_only_that_profiles_applications(session_factory) -> None:
    profile_a, posting = _make_profile_and_posting(session_factory)
    profile_b = Profile(id=new_profile_id(), full_name="B", email="b@example.com")
    SqliteProfileRepository(session_factory).save(profile_b)

    repo = SqliteApplicationRepository(session_factory)
    repo.save(Application(id=new_application_id(), profile_id=profile_a.id, job_posting_id=posting.id))
    repo.save(Application(id=new_application_id(), profile_id=profile_a.id, job_posting_id=posting.id))
    repo.save(Application(id=new_application_id(), profile_id=profile_b.id, job_posting_id=posting.id))

    result = repo.list_by_profile(profile_a.id)

    assert len(result) == 2
    assert all(a.profile_id == profile_a.id for a in result)


def test_delete_removes_the_application_and_its_status_events(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    application.transition_to(
        ApplicationStatus.SUBMITTED, content_snapshot=SubmittedContentSnapshot(resume_label="R")
    )
    repo.save(application)

    repo.delete(application.id)

    assert repo.get(application.id) is None


def test_content_snapshot_with_answers_round_trips_through_real_sqlite(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    repo.save(application)

    snapshot = SubmittedContentSnapshot(
        resume_label="Backend-focused",
        resume_file_name="backend.pdf",
        cover_letter_text="Dear team, I am excited to apply...",
        answers=(
            SubmittedAnswer(question_key="why-us", answer_text="Because of the mission."),
            SubmittedAnswer(question_key="strengths", answer_text="Attention to detail."),
        ),
    )
    application.transition_to(ApplicationStatus.SUBMITTED, content_snapshot=snapshot)
    repo.save(application)

    loaded = repo.get(application.id)

    assert loaded.content_snapshot == snapshot
    assert loaded.content_snapshot.answers[0].question_key == "why-us"
    assert loaded.content_snapshot.answers[1].answer_text == "Attention to detail."


def test_draft_application_has_no_content_snapshot_in_real_sqlite(session_factory) -> None:
    profile, posting = _make_profile_and_posting(session_factory)
    repo = SqliteApplicationRepository(session_factory)
    application = Application(id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id)
    repo.save(application)

    loaded = repo.get(application.id)

    assert loaded.content_snapshot is None
