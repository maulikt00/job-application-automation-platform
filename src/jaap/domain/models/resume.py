"""Resume domain model.

A Resume is a single uploaded resume file belonging to a Profile. Users
may keep several resumes (e.g. tailored for different roles) and select
which one to use per Application.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import ConfigDict, Field, field_validator

from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import ProfileId, ResumeId

_SUPPORTED_RESUME_SUFFIXES = {".pdf", ".doc", ".docx"}


class Resume(Entity):
    """A single resume file belonging to a Profile.

    Attributes:
        id: Unique identifier for this resume.
        profile_id: The Profile this resume belongs to (reference by id only).
        label: A human-readable name to distinguish this resume from others
            (e.g. "Backend-focused", "Full-stack generalist").
        file_path: Path to the resume file on disk. The domain layer only
            validates the file *extension*; it never touches the filesystem
            to check existence -- that is an infrastructure concern.
        uploaded_at: When this resume was added.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: ResumeId
    profile_id: ProfileId
    label: str = Field(..., min_length=1)
    file_path: Path
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("file_path")
    @classmethod
    def _validate_supported_format(cls, value: Path) -> Path:
        if value.suffix.lower() not in _SUPPORTED_RESUME_SUFFIXES:
            allowed = ", ".join(sorted(_SUPPORTED_RESUME_SUFFIXES))
            raise ValueError(
                f"Unsupported resume file type '{value.suffix}'. Allowed types: {allowed}"
            )
        return value
