"""Shared SQLAlchemy declarative base for every ORM model in JAAP."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class all ORM models inherit from.

    Kept in its own module (rather than alongside the model classes) so
    that anything needing the metadata for migrations or `create_all()`
    can import it without pulling in every model definition.
    """
