"""SQLite-backed AnswerRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import Answer, AnswerId, ProfileId
from jaap.infrastructure.database.mappers import answer_mapper
from jaap.infrastructure.database.models import AnswerORM
from jaap.infrastructure.database.session import session_scope


class SqliteAnswerRepository:
    """Satisfies application.interfaces.repositories.AnswerRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, answer_id: AnswerId) -> Answer | None:
        with session_scope(self._session_factory) as session:
            orm = session.get(AnswerORM, answer_id)
            return answer_mapper.to_domain(orm) if orm is not None else None

    def save(self, answer: Answer) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(AnswerORM, answer.id)
            if orm is None:
                orm = AnswerORM(id=answer.id)
                session.add(orm)
            answer_mapper.update_orm(answer, orm)

    def delete(self, answer_id: AnswerId) -> None:
        try:
            with session_scope(self._session_factory) as session:
                orm = session.get(AnswerORM, answer_id)
                if orm is not None:
                    session.delete(orm)
        except IntegrityError as exc:
            raise ReferentialIntegrityError(
                f"Cannot delete Answer {answer_id}: it is still referenced by "
                "an Application (see ADR-0004)."
            ) from exc

    def list_by_profile(self, profile_id: ProfileId) -> list[Answer]:
        with session_scope(self._session_factory) as session:
            stmt = select(AnswerORM).where(AnswerORM.profile_id == profile_id)
            orms = session.scalars(stmt).all()
            return [answer_mapper.to_domain(orm) for orm in orms]
