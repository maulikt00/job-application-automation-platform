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
        address_line1=orm.address_line1,
        address_line2=orm.address_line2,
        city=orm.city,
        state=orm.state,
        postal_code=orm.postal_code,
        country=orm.country,
    )


def update_orm(domain: Profile, orm: ProfileORM) -> None:
    orm.full_name = domain.full_name
    orm.email = domain.email
    orm.phone = domain.phone
    orm.address_line1 = domain.address_line1
    orm.address_line2 = domain.address_line2
    orm.city = domain.city
    orm.state = domain.state
    orm.postal_code = domain.postal_code
    orm.country = domain.country
