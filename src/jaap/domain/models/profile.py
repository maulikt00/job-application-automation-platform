"""Profile domain model.

A Profile represents the person applying for jobs: their identity and
contact information. It is the aggregate root that Resume,
CoverLetterTemplate, and Answer all reference by id, and the entry point
for "whose data is this."
"""

from __future__ import annotations

from pydantic import ConfigDict, EmailStr, Field

from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import ProfileId


class Profile(Entity):
    """The person applying for jobs.

    Attributes:
        id: Unique identifier for this profile.
        full_name: The applicant's full name as it should appear on applications.
        email: Contact email address; validated as a well-formed email.
        phone: Optional contact phone number.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: ProfileId
    full_name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str | None = None
