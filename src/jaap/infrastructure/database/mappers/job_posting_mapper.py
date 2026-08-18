"""JobPosting <-> JobPostingORM mapping."""

from __future__ import annotations

from pydantic import HttpUrl

from jaap.domain.models import JobPosting, JobPostingId
from jaap.infrastructure.database.models import JobPostingORM


def to_domain(orm: JobPostingORM) -> JobPosting:
    return JobPosting(
        id=JobPostingId(orm.id),
        company_name=orm.company_name,
        title=orm.title,
        url=HttpUrl(orm.url),
        platform=orm.platform,
        external_id=orm.external_id,
        platform_metadata=dict(orm.platform_metadata),
        description=orm.description,
    )


def update_orm(domain: JobPosting, orm: JobPostingORM) -> None:
    orm.company_name = domain.company_name
    orm.title = domain.title
    orm.url = str(domain.url)
    orm.platform = domain.platform
    orm.external_id = domain.external_id
    orm.platform_metadata = dict(domain.platform_metadata)
    orm.description = domain.description
