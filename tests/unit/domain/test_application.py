"""Tests for the Application aggregate: the progressive Draft lifecycle
(see ADR-0002), the transition_to() state machine, and the mutation guard
on current_status/status_history (see ADR-0003).
"""

import pytest

from jaap.domain.exceptions import DomainError, InvalidStatusTransitionError
from jaap.domain.models import (
    Application,
    ApplicationStatus,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)


def _make_draft_application() -> Application:
    return Application(
        id=new_application_id(),
        profile_id=new_profile_id(),
        job_posting_id=new_job_posting_id(),
    )


def test_draft_application_requires_only_profile_and_job_posting() -> None:
    application = _make_draft_application()

    assert application.current_status == ApplicationStatus.DRAFT
    assert application.resume_id is None
    assert application.cover_letter_template_id is None
    assert application.answer_ids == ()


def test_draft_application_gets_an_initial_status_history_event() -> None:
    application = _make_draft_application()

    assert len(application.status_history) == 1
    assert application.status_history[0].status == ApplicationStatus.DRAFT
    assert application.status_history[0].changed_at == application.created_at


def test_resume_can_be_attached_after_creation() -> None:
    application = _make_draft_application()
    application.resume_id = new_resume_id()

    assert application.resume_id is not None


def test_valid_transition_updates_status_and_history() -> None:
    application = _make_draft_application()

    application.transition_to(ApplicationStatus.SUBMITTED, note="Submitted via Greenhouse")

    assert application.current_status == ApplicationStatus.SUBMITTED
    assert len(application.status_history) == 2
    assert application.status_history[-1].status == ApplicationStatus.SUBMITTED
    assert application.status_history[-1].note == "Submitted via Greenhouse"


def test_full_happy_path_transition_sequence() -> None:
    application = _make_draft_application()

    application.transition_to(ApplicationStatus.SUBMITTED)
    application.transition_to(ApplicationStatus.INTERVIEWING)
    application.transition_to(ApplicationStatus.OFFER)

    assert application.current_status == ApplicationStatus.OFFER
    assert [event.status for event in application.status_history] == [
        ApplicationStatus.DRAFT,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
    ]


def test_invalid_transition_raises_and_leaves_state_unchanged() -> None:
    application = _make_draft_application()

    with pytest.raises(InvalidStatusTransitionError):
        application.transition_to(ApplicationStatus.OFFER)

    assert application.current_status == ApplicationStatus.DRAFT
    assert len(application.status_history) == 1


def test_terminal_statuses_allow_no_further_transitions() -> None:
    application = _make_draft_application()
    application.transition_to(ApplicationStatus.WITHDRAWN)

    with pytest.raises(InvalidStatusTransitionError):
        application.transition_to(ApplicationStatus.SUBMITTED)


def test_invalid_status_transition_error_message_names_both_statuses() -> None:
    application = _make_draft_application()

    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        application.transition_to(ApplicationStatus.INTERVIEWING)

    assert exc_info.value.current_status == ApplicationStatus.DRAFT
    assert exc_info.value.attempted_status == ApplicationStatus.INTERVIEWING
    assert "draft" in str(exc_info.value)
    assert "interviewing" in str(exc_info.value)


def test_direct_assignment_to_current_status_is_rejected() -> None:
    application = _make_draft_application()

    with pytest.raises(DomainError):
        application.current_status = ApplicationStatus.SUBMITTED

    # Rejected assignment must not have partially applied.
    assert application.current_status == ApplicationStatus.DRAFT


def test_direct_assignment_to_status_history_is_rejected() -> None:
    application = _make_draft_application()

    with pytest.raises(DomainError):
        application.status_history = ()

    assert len(application.status_history) == 1


def test_non_protected_fields_remain_freely_settable() -> None:
    application = _make_draft_application()

    # resume_id/cover_letter_template_id/answer_ids carry no cross-field
    # invariant, so direct assignment is still the sanctioned path for them.
    application.resume_id = new_resume_id()
    assert application.resume_id is not None
