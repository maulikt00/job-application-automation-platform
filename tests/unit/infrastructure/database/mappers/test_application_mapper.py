"""Tests for application_mapper: the append-only status_history diff and
the full delete-and-recreate answer_associations strategy (see the
module's own docstring and ADR-0005). Pure Python -- ORM relationship
collections behave as ordinary lists even on objects never added to a
session, so no database is needed here.
"""

from __future__ import annotations

from jaap.domain.models import (
    Application,
    ApplicationStatus,
    new_answer_id,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.infrastructure.database.mappers import application_mapper
from jaap.infrastructure.database.models import ApplicationORM


def _make_draft() -> Application:
    return Application(
        id=new_application_id(), profile_id=new_profile_id(), job_posting_id=new_job_posting_id()
    )


def test_draft_application_round_trips_with_optional_fields_unset() -> None:
    domain = _make_draft()

    orm = ApplicationORM(id=domain.id)
    application_mapper.update_orm(domain, orm)
    result = application_mapper.to_domain(orm)

    assert result == domain
    assert result.resume_id is None
    assert result.cover_letter_template_id is None
    assert result.answer_ids == ()
    assert [e.status for e in result.status_history] == [ApplicationStatus.DRAFT]


def test_status_history_is_inserted_once_and_not_duplicated_on_repeated_saves() -> None:
    domain = _make_draft()
    orm = ApplicationORM(id=domain.id)

    application_mapper.update_orm(domain, orm)
    assert len(orm.status_events) == 1

    # Saving again with no new transitions must not duplicate the
    # existing DRAFT event.
    application_mapper.update_orm(domain, orm)
    assert len(orm.status_events) == 1


def test_new_transitions_are_appended_not_replacing_existing_history() -> None:
    domain = _make_draft()
    orm = ApplicationORM(id=domain.id)
    application_mapper.update_orm(domain, orm)

    domain.transition_to(ApplicationStatus.SUBMITTED)
    application_mapper.update_orm(domain, orm)
    assert [e.status for e in orm.status_events] == ["draft", "submitted"]
    assert [e.sequence for e in orm.status_events] == [0, 1]

    domain.transition_to(ApplicationStatus.INTERVIEWING)
    application_mapper.update_orm(domain, orm)
    assert [e.status for e in orm.status_events] == ["draft", "submitted", "interviewing"]
    assert [e.sequence for e in orm.status_events] == [0, 1, 2]


def test_update_orm_does_not_touch_answer_associations() -> None:
    # answer_associations reconciliation requires a mid-operation
    # session.flush() (see application_mapper's module docstring and
    # SqliteApplicationRepository.save()), so it deliberately lives in
    # the repository, not here. This test locks in that boundary: calling
    # update_orm() alone must never add/remove/modify answer_associations,
    # even when the domain object's answer_ids has changed.
    domain = _make_draft()
    orm = ApplicationORM(id=domain.id)

    domain.answer_ids = (new_answer_id(), new_answer_id())
    application_mapper.update_orm(domain, orm)

    assert orm.answer_associations == []


def test_to_domain_preserves_answer_association_order() -> None:
    # Exercises to_domain() only, with answer_associations populated
    # directly (not via update_orm, which doesn't touch them -- see the
    # test above). Real end-to-end save/reload ordering against a
    # database is covered separately in
    # test_sqlite_application_repository.py, since that's where the
    # actual reconciliation logic lives.
    from jaap.infrastructure.database.models import ApplicationAnswerORM

    domain = _make_draft()
    orm = ApplicationORM(id=domain.id)
    application_mapper.update_orm(domain, orm)

    ids = [new_answer_id() for _ in range(3)]
    for position, answer_id in enumerate(ids):
        orm.answer_associations.append(ApplicationAnswerORM(answer_id=answer_id, position=position))

    result = application_mapper.to_domain(orm)
    assert result.answer_ids == tuple(ids)


def test_optional_resume_and_template_ids_round_trip_when_set() -> None:
    domain = _make_draft()
    domain.resume_id = new_resume_id()

    orm = ApplicationORM(id=domain.id)
    application_mapper.update_orm(domain, orm)
    result = application_mapper.to_domain(orm)

    assert result.resume_id == domain.resume_id
    assert result.cover_letter_template_id is None
