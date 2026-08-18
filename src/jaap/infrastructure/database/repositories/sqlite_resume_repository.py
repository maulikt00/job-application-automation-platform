"""SQLite-backed ResumeRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import ProfileId, Resume, ResumeId
from jaap.infrastructure.database.mappers import resume_mapper
from jaap.infrastructure.database.models import ResumeORM
from jaap.infrastructure.database.session import session_scope


class SqliteResumeRepository:
    """Satisfies application.interfaces.repositories.ResumeRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, resume_id: ResumeId) -> Resume | None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ResumeORM, resume_id)
            return resume_mapper.to_domain(orm) if orm is not None else None

    def save(self, resume: Resume) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ResumeORM, resume.id)
            if orm is None:
                orm = ResumeORM(id=resume.id)
                session.add(orm)
            resume_mapper.update_orm(resume, orm)

    def delete(self, resume_id: ResumeId) -> None:
        try:
            with session_scope(self._session_factory) as session:
                orm = session.get(ResumeORM, resume_id)
                if orm is not None:
                    session.delete(orm)
        except IntegrityError as exc:
            raise ReferentialIntegrityError(
                f"Cannot delete Resume {resume_id}: it is still referenced by "
                "an Application (see ADR-0004)."
            ) from exc

    def list_by_profile(self, profile_id: ProfileId) -> list[Resume]:
        with session_scope(self._session_factory) as session:
            stmt = select(ResumeORM).where(ResumeORM.profile_id == profile_id)
            orms = session.scalars(stmt).all()
            return [resume_mapper.to_domain(orm) for orm in orms]
