"""CoverLetterTemplate domain model.

A reusable cover letter template belonging to a Profile. Templates may
contain placeholder text (e.g. "{{company_name}}") intended to be filled
in per-application. Placeholder substitution itself is an application- or
infrastructure-layer concern (e.g. an AI-assisted generation use case in
Phase 3), not something the domain model performs.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import CoverLetterTemplateId, ProfileId


class CoverLetterTemplate(Entity):
    """A reusable cover letter template belonging to a Profile.

    Attributes:
        id: Unique identifier for this template.
        profile_id: The Profile this template belongs to.
        name: A human-readable name for the template.
        body_template: The template body text, which may include placeholders.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: CoverLetterTemplateId
    profile_id: ProfileId
    name: str = Field(..., min_length=1)
    body_template: str = Field(..., min_length=1)
