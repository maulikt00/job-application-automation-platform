"""SQLite-backed ApplicationRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.models import Application, ApplicationId, ProfileId
from jaap.infrastructure.database.mappers import application_mapper
from jaap.infrastructure.database.models import ApplicationAnswerORM, ApplicationORM
from jaap.infrastructure.database.session import session_scope


class SqliteApplicationRepository:
    """Satisfies application.interfaces.repositories.ApplicationRepository.

    No RESTRICT/IntegrityError translation is needed on delete: an
    Application's own children (status_events, answer_associations) all
    cascade on delete (see models.py) -- RESTRICT only applies to the
    other direction (deleting a Resume/Template/Answer that an
    Application still references), which is handled in those
    repositories' delete() methods, not here.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, application_id: ApplicationId) -> Application | None:
        with session_scope(self._session_factory) as session:
            # status_events/answer_associations are lazy="selectin" on
            # ApplicationORM (see models.py / ADR-0004), so this .get()
            # already eager-loads everything to_domain() needs.
            orm = session.get(ApplicationORM, application_id)
            return application_mapper.to_domain(orm) if orm is not None else None

    def save(self, application: Application) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ApplicationORM, application.id)
            if orm is None:
                orm = ApplicationORM(id=application.id)
                session.add(orm)

            # Handles every field except answer_associations (see
            # application_mapper.update_orm()'s docstring for why).
            application_mapper.update_orm(application, orm)

            # answer_ids: full delete-and-recreate on every save (see
            # ADR-0005 / application_mapper's module docstring). The
            # explicit flush() between clear() and re-append() is
            # required, not optional: without it, SQLAlchemy's
            # unit-of-work can conflate a removed-then-re-added
            # association sharing the same (application_id, answer_id)
            # composite primary key as an in-place UPDATE rather than a
            # delete-then-insert, which collides with the
            # (application_id, position) unique constraint mid-flush.
            # Verified against a real failure during Milestone 5's
            # development -- do not remove this flush() as a "simplification."
            orm.answer_associations.clear()
            session.flush()
            for position, answer_id in enumerate(application.answer_ids):
                orm.answer_associations.append(
                    ApplicationAnswerORM(answer_id=answer_id, position=position)
                )

    def delete(self, application_id: ApplicationId) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ApplicationORM, application_id)
            if orm is not None:
                session.delete(orm)

    def list_by_profile(self, profile_id: ProfileId) -> list[Application]:
        with session_scope(self._session_factory) as session:
            stmt = select(ApplicationORM).where(ApplicationORM.profile_id == profile_id)
            orms = session.scalars(stmt).all()
            return [application_mapper.to_domain(orm) for orm in orms]
