"""CoverLetterTemplate <-> CoverLetterTemplateORM mapping."""

from __future__ import annotations

from jaap.domain.models import CoverLetterTemplate, CoverLetterTemplateId, ProfileId
from jaap.infrastructure.database.models import CoverLetterTemplateORM


def to_domain(orm: CoverLetterTemplateORM) -> CoverLetterTemplate:
    return CoverLetterTemplate(
        id=CoverLetterTemplateId(orm.id),
        profile_id=ProfileId(orm.profile_id),
        name=orm.name,
        body_template=orm.body_template,
    )


def update_orm(domain: CoverLetterTemplate, orm: CoverLetterTemplateORM) -> None:
    orm.profile_id = domain.profile_id
    orm.name = domain.name
    orm.body_template = domain.body_template
