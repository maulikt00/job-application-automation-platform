"""SQLite-backed ProfileRepository implementation."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from jaap.domain.models import Profile, ProfileId
from jaap.infrastructure.database.mappers import profile_mapper
from jaap.infrastructure.database.models import ProfileORM
from jaap.infrastructure.database.session import session_scope


class SqliteProfileRepository:
    """Satisfies application.interfaces.repositories.ProfileRepository."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, profile_id: ProfileId) -> Profile | None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ProfileORM, profile_id)
            return profile_mapper.to_domain(orm) if orm is not None else None

    def save(self, profile: Profile) -> None:
        with session_scope(self._session_factory) as session:
            orm = session.get(ProfileORM, profile.id)
            if orm is None:
                orm = ProfileORM(id=profile.id)
                session.add(orm)
            profile_mapper.update_orm(profile, orm)

    def delete(self, profile_id: ProfileId) -> None:
        # Profile -> Resume/CoverLetterTemplate/Answer/Application all
        # cascade on delete (see models.py), so no RESTRICT/IntegrityError
        # translation is needed here, unlike Resume/Template/Answer.
        with session_scope(self._session_factory) as session:
            orm = session.get(ProfileORM, profile_id)
            if orm is not None:
                session.delete(orm)
