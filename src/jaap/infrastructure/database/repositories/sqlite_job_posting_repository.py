"""SQLite-backed JobPostingRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.models import JobPosting, JobPostingId
from jaap.infrastructure.database.mappers import job_posting_mapper
from jaap.infrastructure.database.models import JobPostingORM
from jaap.infrastructure.database.session import session_scope


class SqliteJobPostingRepository:
    """Satisfies application.interfaces.repositories.JobPostingRepository.

    No RESTRICT/IntegrityError translation is needed on delete: deleting a
    JobPosting cascades to its Applications (see models.py), it isn't
    RESTRICTed like Resume/CoverLetterTemplate/Answer are.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, job_posting_id: JobPostingId) -> JobPosting | None:
        with session_scope(self._session_factory) as session:
            orm = session.get(JobPostingORM, job_posting_id)
            return job_posting_mapper.to_domain(orm) if orm is not None else None

    def save(self, job_posting: JobPosting) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(JobPostingORM, job_posting.id)
            if orm is None:
                orm = JobPostingORM(id=job_posting.id)
                session.add(orm)
            job_posting_mapper.update_orm(job_posting, orm)

    def delete(self, job_posting_id: JobPostingId) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(JobPostingORM, job_posting_id)
            if orm is not None:
                session.delete(orm)

    def find_by_platform_and_external_id(
        self, platform: str, external_id: str
    ) -> JobPosting | None:
        with session_scope(self._session_factory) as session:
            stmt = select(JobPostingORM).where(
                JobPostingORM.platform == platform,
                JobPostingORM.external_id == external_id,
            )
            orm = session.scalars(stmt).first()
            return job_posting_mapper.to_domain(orm) if orm is not None else None
