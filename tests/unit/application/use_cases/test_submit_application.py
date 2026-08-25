"""Tests for SubmitApplicationUseCase, including the submitted content
snapshot (Milestone 13/ADR-0013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.application.exceptions import (
    AnswerNotFoundError,
    ApplicationNotFoundError,
    ApplicationNotReadyForSubmissionError,
    CoverLetterTemplateNotFoundError,
    ResumeNotFoundError,
)
from jaap.application.use_cases.submit_application import SubmitApplicationUseCase
from jaap.domain.exceptions import InvalidStatusTransitionError
from jaap.domain.models import (
    Answer,
    Application,
    ApplicationStatus,
    CoverLetterTemplate,
    Resume,
    new_answer_id,
    new_application_id,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.domain.models.application import SubmittedContentSnapshot
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeApplicationRepository,
    FakeCoverLetterTemplateRepository,
    FakeResumeRepository,
)


def _make_draft_application(*, with_resume: bool) -> Application:
    return Application(
        id=new_application_id(),
        profile_id=new_profile_id(),
        job_posting_id=new_job_posting_id(),
        resume_id=new_resume_id() if with_resume else None,
    )


def _make_use_case():
    application_repo = FakeApplicationRepository()
    resume_repo = FakeResumeRepository()
    answer_repo = FakeAnswerRepository()
    template_repo = FakeCoverLetterTemplateRepository()
    use_case = SubmitApplicationUseCase(application_repo, resume_repo, answer_repo, template_repo)
    return use_case, application_repo, resume_repo, answer_repo, template_repo


def test_submits_a_draft_application_with_a_resume_attached() -> None:
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="Backend", file_path=Path("backend.pdf"),
    )
    resume_repo.save(resume)
    app_repo.save(application)

    result = use_case.execute(application.id)

    assert result.current_status == ApplicationStatus.SUBMITTED
    assert app_repo.get(application.id).current_status == ApplicationStatus.SUBMITTED


def test_raises_not_ready_when_no_resume_is_attached() -> None:
    use_case, app_repo, _, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=False)
    app_repo.save(application)

    with pytest.raises(ApplicationNotReadyForSubmissionError):
        use_case.execute(application.id)

    # Must not have partially transitioned.
    assert app_repo.get(application.id).current_status == ApplicationStatus.DRAFT


def test_raises_application_not_found_for_missing_id() -> None:
    use_case, _, _, _, _ = _make_use_case()

    with pytest.raises(ApplicationNotFoundError):
        use_case.execute(new_application_id())


def test_raises_resume_not_found_when_resume_id_does_not_resolve() -> None:
    # A defensive path: RESTRICT foreign keys should make this
    # unreachable in real persistence, but the use case must still
    # handle it explicitly rather than crash unhelpfully.
    use_case, app_repo, _, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    app_repo.save(application)  # resume was never saved to resume_repo

    with pytest.raises(ResumeNotFoundError):
        use_case.execute(application.id)


def test_invalid_status_transition_propagates_unmodified() -> None:
    # Submitting an already-SUBMITTED application is a structural
    # invariant violation (domain layer's job, per ADR-0002/0003), not a
    # business rule this use case re-implements -- transition_to()
    # itself must be the one to reject it.
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    application.transition_to(
        ApplicationStatus.SUBMITTED, content_snapshot=SubmittedContentSnapshot(resume_label="R")
    )
    app_repo.save(application)

    with pytest.raises(InvalidStatusTransitionError):
        use_case.execute(application.id)


def test_content_snapshot_captures_resume_label_and_file_name() -> None:
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="Backend-focused", file_path=Path("resumes/backend.pdf"),
    )
    resume_repo.save(resume)
    app_repo.save(application)

    result = use_case.execute(application.id)

    assert result.content_snapshot.resume_label == "Backend-focused"
    assert result.content_snapshot.resume_file_name == "backend.pdf"


def test_content_snapshot_captures_literal_answer_text() -> None:
    use_case, app_repo, resume_repo, answer_repo, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    answer = Answer(
        id=new_answer_id(), profile_id=application.profile_id,
        question_key="why-us", answer_text="Because of the mission.",
    )
    answer_repo.save(answer)
    application.answer_ids = (answer.id,)
    app_repo.save(application)

    result = use_case.execute(application.id)

    assert result.content_snapshot.answers[0].question_key == "why-us"
    assert result.content_snapshot.answers[0].answer_text == "Because of the mission."


def test_raises_answer_not_found_when_an_answer_id_does_not_resolve() -> None:
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    application.answer_ids = (new_answer_id(),)  # never saved
    app_repo.save(application)

    with pytest.raises(AnswerNotFoundError):
        use_case.execute(application.id)


def test_content_snapshot_resolves_cover_letter_text_from_template() -> None:
    use_case, app_repo, resume_repo, _, template_repo = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    template = CoverLetterTemplate(
        id=new_cover_letter_template_id(), profile_id=application.profile_id,
        name="Standard", body_template="Dear team...",
    )
    template_repo.save(template)
    application.cover_letter_template_id = template.id
    app_repo.save(application)

    result = use_case.execute(application.id)

    assert result.content_snapshot.cover_letter_text == "Dear team..."


def test_raises_cover_letter_template_not_found_when_id_does_not_resolve() -> None:
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    application.cover_letter_template_id = new_cover_letter_template_id()  # never saved
    app_repo.save(application)

    with pytest.raises(CoverLetterTemplateNotFoundError):
        use_case.execute(application.id)


def test_cover_letter_text_override_is_used_even_with_no_template_set() -> None:
    # The Milestone 16 case: AI-generated, one-off cover letter text that
    # was never saved as a reusable CoverLetterTemplate at all.
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    app_repo.save(application)

    result = use_case.execute(
        application.id, cover_letter_text_override="AI-generated bespoke text."
    )

    assert result.content_snapshot.cover_letter_text == "AI-generated bespoke text."


def test_cover_letter_text_override_wins_even_when_a_template_is_also_set() -> None:
    use_case, app_repo, resume_repo, _, template_repo = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    template = CoverLetterTemplate(
        id=new_cover_letter_template_id(), profile_id=application.profile_id,
        name="Standard", body_template="Template text, should NOT be used.",
    )
    template_repo.save(template)
    application.cover_letter_template_id = template.id
    app_repo.save(application)

    result = use_case.execute(application.id, cover_letter_text_override="Override wins.")

    assert result.content_snapshot.cover_letter_text == "Override wins."


def test_content_snapshot_cover_letter_text_is_none_when_neither_is_set() -> None:
    use_case, app_repo, resume_repo, _, _ = _make_use_case()
    application = _make_draft_application(with_resume=True)
    resume = Resume(
        id=application.resume_id, profile_id=application.profile_id,
        label="R", file_path=Path("r.pdf"),
    )
    resume_repo.save(resume)
    app_repo.save(application)

    result = use_case.execute(application.id)

    assert result.content_snapshot.cover_letter_text is None
