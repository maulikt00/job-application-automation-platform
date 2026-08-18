"""Domain <-> ORM translation, one module per aggregate.

Kept separate from the repository classes so this translation logic is
independently unit-testable with plain Python objects -- no database
required. Repositories (infrastructure/database/repositories/) own
session/query orchestration and call into these; mappers never touch a
Session themselves.

Each module exposes two functions:
  - `to_domain(orm) -> Domain`: build a fresh domain object from a loaded
    ORM instance.
  - `update_orm(domain, orm) -> None`: mutate an existing (or
    newly-constructed but not-yet-added) ORM instance's fields to match
    the domain object, for both insert and update. Never sets `id` --
    the repository is responsible for that, since it's the one deciding
    whether this is an insert or an update.
"""
