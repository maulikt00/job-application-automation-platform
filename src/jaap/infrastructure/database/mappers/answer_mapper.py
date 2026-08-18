"""Answer <-> AnswerORM mapping."""

from __future__ import annotations

from jaap.domain.models import Answer, AnswerId, ProfileId
from jaap.infrastructure.database.models import AnswerORM


def to_domain(orm: AnswerORM) -> Answer:
    return Answer(
        id=AnswerId(orm.id),
        profile_id=ProfileId(orm.profile_id),
        question_key=orm.question_key,
        answer_text=orm.answer_text,
        tags=list(orm.tags),
    )


def update_orm(domain: Answer, orm: AnswerORM) -> None:
    orm.profile_id = domain.profile_id
    orm.question_key = domain.question_key
    orm.answer_text = domain.answer_text
    orm.tags = list(domain.tags)
