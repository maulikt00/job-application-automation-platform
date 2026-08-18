"""SQLite-backed CoverLetterTemplateRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import CoverLetterTemplate, CoverLetterTemplateId, ProfileId
from jaap.infrastructure.database.mappers import cover_letter_template_mapper
from jaap.infrastructure.database.models import CoverLetterTemplateORM
from jaap.infrastructure.database.session import session_scope


class SqliteCoverLetterTemplateRepository:
    """Satisfies application.interfaces.repositories.CoverLetterTemplateRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, template_id: CoverLetterTemplateId) -> CoverLetterTemplate | None:
        with session_scope(self._session_factory) as session:
            orm = session.get(CoverLetterTemplateORM, template_id)
            return cover_letter_template_mapper.to_domain(orm) if orm is not None else None

    def save(self, template: CoverLetterTemplate) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(CoverLetterTemplateORM, template.id)
            if orm is None:
                orm = CoverLetterTemplateORM(id=template.id)
                session.add(orm)
            cover_letter_template_mapper.update_orm(template, orm)

    def delete(self, template_id: CoverLetterTemplateId) -> None:
        try:
            with session_scope(self._session_factory) as session:
                orm = session.get(CoverLetterTemplateORM, template_id)
                if orm is not None:
                    session.delete(orm)
        except IntegrityError as exc:
            raise ReferentialIntegrityError(
                f"Cannot delete CoverLetterTemplate {template_id}: it is still "
                "referenced by an Application (see ADR-0004)."
            ) from exc

    def list_by_profile(self, profile_id: ProfileId) -> list[CoverLetterTemplate]:
        with session_scope(self._session_factory) as session:
            stmt = select(CoverLetterTemplateORM).where(
                CoverLetterTemplateORM.profile_id == profile_id
            )
            orms = session.scalars(stmt).all()
            return [cover_letter_template_mapper.to_domain(orm) for orm in orms]
