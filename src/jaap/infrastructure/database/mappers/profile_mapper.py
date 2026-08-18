"""Profile <-> ProfileORM mapping."""

from __future__ import annotations

from jaap.domain.models import Profile, ProfileId
from jaap.infrastructure.database.models import ProfileORM


def to_domain(orm: ProfileORM) -> Profile:
    return Profile(
        id=ProfileId(orm.id),
        full_name=orm.full_name,
        email=orm.email,
        phone=orm.phone,
    )


def update_orm(domain: Profile, orm: ProfileORM) -> None:
    orm.full_name = domain.full_name
    orm.email = domain.email
    orm.phone = domain.phone
