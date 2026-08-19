"""Tests for SubmitApplicationUseCase."""

from __future__ import annotations

import pytest

from jaap.application.exceptions import (
    ApplicationNotFoundError,
    ApplicationNotReadyForSubmissionError,
)
from jaap.application.use_cases.submit_application import SubmitApplicationUseCase
from jaap.domain.exceptions import InvalidStatusTransitionError
from jaap.domain.models import (
    Application,
    ApplicationStatus,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from tests.unit.application.use_cases.fakes import FakeApplicationRepository


def _make_draft_application(*, with_resume: bool) -> Application:
    return Application(
        id=new_application_id(),
        profile_id=new_profile_id(),
        job_posting_id=new_job_posting_id(),
        resume_id=new_resume_id() if with_resume else None,
    )


def test_submits_a_draft_application_with_a_resume_attached() -> None:
    repo = FakeApplicationRepository()
    application = _make_draft_application(with_resume=True)
    repo.save(application)
    use_case = SubmitApplicationUseCase(repo)

    result = use_case.execute(application.id)

    assert result.current_status == ApplicationStatus.SUBMITTED
    assert repo.get(application.id).current_status == ApplicationStatus.SUBMITTED


def test_raises_not_ready_when_no_resume_is_attached() -> None:
    repo = FakeApplicationRepository()
    application = _make_draft_application(with_resume=False)
    repo.save(application)
    use_case = SubmitApplicationUseCase(repo)

    with pytest.raises(ApplicationNotReadyForSubmissionError):
        use_case.execute(application.id)

    # Must not have partially transitioned.
    assert repo.get(application.id).current_status == ApplicationStatus.DRAFT


def test_raises_application_not_found_for_missing_id() -> None:
    repo = FakeApplicationRepository()
    use_case = SubmitApplicationUseCase(repo)

    with pytest.raises(ApplicationNotFoundError):
        use_case.execute(new_application_id())


def test_invalid_status_transition_propagates_unmodified() -> None:
    # Submitting an already-SUBMITTED application is a structural
    # invariant violation (domain layer's job, per ADR-0002/0003), not a
    # business rule this use case re-implements -- transition_to()
    # itself must be the one to reject it.
    repo = FakeApplicationRepository()
    application = _make_draft_application(with_resume=True)
    application.transition_to(ApplicationStatus.SUBMITTED)
    repo.save(application)
    use_case = SubmitApplicationUseCase(repo)

    with pytest.raises(InvalidStatusTransitionError):
        use_case.execute(application.id)
