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
        address_line1: Optional street address.
        address_line2: Optional second address line (apartment, suite, etc.).
        city: Optional city.
        state: Optional state/region/province.
        postal_code: Optional postal/ZIP code.
        country: Optional country.

    Address fields were added after real-world validation confirmed
    real application forms (Workday's, ADR-0038) commonly ask for one --
    all optional, matching `phone`'s existing pattern, since not every
    application needs one and not every person will want to provide it
    upfront.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: ProfileId
    full_name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
