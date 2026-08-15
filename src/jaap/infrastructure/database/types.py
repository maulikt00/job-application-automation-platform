"""Custom SQLAlchemy column types.

SQLite has no native timezone-aware datetime type -- a plain DateTime
column will silently store and return naive datetimes unless something
normalizes the boundary explicitly. Left alone, a freshly created domain
object (always timezone-aware, per the domain models) and one reloaded
from the database would compare unequal in subtle, hard-to-reproduce
ways. UTCDateTime decides this once, here, rather than leaving it to
each repository to handle consistently on its own.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Stores timezone-aware UTC datetimes as naive UTC under the hood,
    and re-attaches UTC tzinfo on load, so a save/load round trip always
    returns a value equal to what was stored.

    Rejects naive datetimes on the way in -- the domain layer always
    produces timezone-aware datetimes (see Application, Resume, etc.), so
    a naive datetime arriving here indicates a bug upstream, not a case to
    silently accept and guess about.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "UTCDateTime requires a timezone-aware datetime; received a naive one."
            )
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
