"""Resume <-> ResumeORM mapping."""

from __future__ import annotations

from pathlib import Path

from jaap.domain.models import ProfileId, Resume, ResumeId
from jaap.infrastructure.database.models import ResumeORM


def to_domain(orm: ResumeORM) -> Resume:
    return Resume(
        id=ResumeId(orm.id),
        profile_id=ProfileId(orm.profile_id),
        label=orm.label,
        file_path=Path(orm.file_path),
        uploaded_at=orm.uploaded_at,
    )


def update_orm(domain: Resume, orm: ResumeORM) -> None:
    orm.profile_id = domain.profile_id
    orm.label = domain.label
    orm.file_path = str(domain.file_path)
    orm.uploaded_at = domain.uploaded_at
