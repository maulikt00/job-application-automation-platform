"""Application <-> ApplicationORM mapping.

The most involved mapper, since Application carries a status history and
a set of answer associations that need different reconciliation
strategies on save (see the Milestone 5 design discussion and
docs/adr/0005-repository-interfaces-and-mapping-strategy.md):

  - `status_history` is append-only in the domain model (Application.
    transition_to() only ever adds events, per ADR-0002/0003). On save,
    only events beyond what's already persisted are inserted -- a simple
    length-based diff is correct because the domain object's history is
    never shorter or reordered relative to what's in the database.
    Handled here, in `update_orm()`.
  - `answer_ids` is NOT append-only -- a use case could remove an answer
    before submission, not just add one. Every save fully replaces the
    persisted associations from the domain object's current `answer_ids`
    tuple, rather than computing a precise add/remove/reorder diff.
    Simpler and correct at this project's scale; the only thing lost is
    per-association "when was this answer first attached" history, which
    nothing currently needs (see ADR-0005 for the full trade-off).
    **NOT handled here** -- see `update_orm()`'s docstring for why this
    one specifically lives in the repository instead.

`to_domain` relies on `ApplicationORM.status_events` and
`.answer_associations` already being ordered (by `sequence`/`position`
respectively -- see models.py's `order_by` on both relationships), so no
sorting happens here; the ORM layer already guarantees the order.
"""

from __future__ import annotations

from jaap.domain.models import (
    AnswerId,
    Application,
    ApplicationId,
    ApplicationStatus,
    ApplicationStatusEvent,
    CoverLetterTemplateId,
    JobPostingId,
    ProfileId,
    ResumeId,
)
from jaap.infrastructure.database.models import (
    ApplicationORM,
    ApplicationStatusEventORM,
)


def to_domain(orm: ApplicationORM) -> Application:
    status_history = tuple(
        ApplicationStatusEvent(
            status=ApplicationStatus(event.status),
            changed_at=event.changed_at,
            note=event.note,
        )
        for event in orm.status_events
    )
    answer_ids = tuple(AnswerId(assoc.answer_id) for assoc in orm.answer_associations)

    return Application(
        id=ApplicationId(orm.id),
        profile_id=ProfileId(orm.profile_id),
        job_posting_id=JobPostingId(orm.job_posting_id),
        resume_id=ResumeId(orm.resume_id) if orm.resume_id is not None else None,
        cover_letter_template_id=(
            CoverLetterTemplateId(orm.cover_letter_template_id)
            if orm.cover_letter_template_id is not None
            else None
        ),
        answer_ids=answer_ids,
        current_status=ApplicationStatus(orm.current_status),
        status_history=status_history,
        created_at=orm.created_at,
    )


def update_orm(domain: Application, orm: ApplicationORM) -> None:
    """Updates every field except `answer_ids`.

    `answer_associations` is deliberately NOT handled here: replacing it
    safely requires an explicit `session.flush()` between clearing the
    old associations and adding new ones (SQLAlchemy's unit-of-work can
    otherwise conflate a removed-then-re-added row sharing the same
    composite primary key as an in-place UPDATE, which collides with the
    (application_id, position) unique constraint mid-flush). Since
    mappers never touch a Session, that reconciliation lives in
    SqliteApplicationRepository.save() instead -- see its docstring.
    """
    orm.profile_id = domain.profile_id
    orm.job_posting_id = domain.job_posting_id
    orm.resume_id = domain.resume_id
    orm.cover_letter_template_id = domain.cover_letter_template_id
    orm.current_status = domain.current_status.value
    orm.created_at = domain.created_at

    # status_history: append-only tail-insert (see module docstring).
    already_persisted = len(orm.status_events)
    new_events = domain.status_history[already_persisted:]
    for offset, event in enumerate(new_events):
        orm.status_events.append(
            ApplicationStatusEventORM(
                sequence=already_persisted + offset,
                status=event.status.value,
                changed_at=event.changed_at,
                note=event.note,
            )
        )
