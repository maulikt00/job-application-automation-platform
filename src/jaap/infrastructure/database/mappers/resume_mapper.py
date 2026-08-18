"""Resume <-> ResumeORM mapping.

`file_path` is stored using `.as_posix()`, not `str()`: `str(Path(...))`
renders using the OS's native separator (backslashes on Windows), so a
path stored from a Windows machine would fail to parse back correctly
as a path on Linux/Mac, and vice versa. `.as_posix()` always normalizes
to forward slashes on write; `Path(...)` on read parses forward
slashes correctly regardless of OS, so storage is OS-agnostic in both
directions.
"""

from __future__ import annotations

from pathlib import Path

from jaap.domain.models import ProfileId, Resume, ResumeId
from jaap.infrastructure.database.models import ResumeORM


def to_domain(orm: ResumeORM) -> Resume:
    return Resume(
        id=ResumeId(orm.id),
        profile_id=ProfileId(orm.profile_id),
        label=orm.label,
        file_path=Path(orm.file_path),
        uploaded_at=orm.uploaded_at,
    )


def update_orm(domain: Resume, orm: ResumeORM) -> None:
    orm.profile_id = domain.profile_id
    orm.label = domain.label
    orm.file_path = domain.file_path.as_posix() #str(domain.file_path)
    orm.uploaded_at = domain.uploaded_at
