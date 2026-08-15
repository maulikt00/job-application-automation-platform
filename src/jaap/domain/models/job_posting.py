"""JobPosting domain model.

A JobPosting represents a real-world job listing, typically sourced from
an external website via a connector (Phase 4) or entered manually. It is
intentionally *not* owned by any Profile -- a posting exists independent
of who might apply to it, which keeps this model ready for a future
multi-user version of JAAP without needing to be restructured.

See docs/adr/0003-entity-identity-and-connector-extensibility.md for why
`platform` is an open string rather than a closed enum, and why
`external_id`/`platform_metadata` exist as a connector extension point.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field, HttpUrl, field_validator

from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import JobPostingId


class JobPlatform:
    """Suggested, non-exhaustive platform identifier constants.

    `JobPosting.platform` accepts any non-empty string so that a new
    connector (Milestone 19+) can introduce support for a job site by
    adding a connector file, without needing to modify this domain model
    or add a new enum member here. These constants exist purely for
    convenience/typo-avoidance when a connector's platform is one we
    already know about -- they are not an exhaustive, closed set.
    """

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    LINKEDIN = "linkedin"
    OTHER = "other"


class JobPosting(Entity):
    """A job listing a user might apply to.

    Attributes:
        id: Unique identifier for this job posting (JAAP-internal).
        company_name: The hiring company's name.
        title: The job title.
        url: Link to the original posting.
        platform: An open-ended identifier for the website/ATS this
            posting was sourced from (e.g. "greenhouse", "linkedin"). See
            `JobPlatform` for suggested values; new connectors may
            introduce new platform strings without a domain model change.
        external_id: The source platform's own identifier for this
            posting (e.g. a Greenhouse job token, a LinkedIn job URN),
            used by connectors as a stable dedup/re-fetch key -- more
            reliable than `url`, which can vary across scrapes due to
            redirects, tracking parameters, or URL normalization.
        platform_metadata: An open, connector-defined bag of additional
            platform-specific data (e.g. board name, req number) that
            doesn't warrant its own dedicated field. Keeping this as an
            open mapping -- rather than adding a field per connector --
            is what lets Milestone 19+ add new connectors without
            modifying this model.
        description: The full job description text.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: JobPostingId
    company_name: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    url: HttpUrl
    platform: str = Field(default=JobPlatform.OTHER, min_length=1)
    external_id: str | None = None
    platform_metadata: dict[str, str] = Field(default_factory=dict)
    description: str = ""

    @field_validator("platform")
    @classmethod
    def _normalize_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("platform must contain at least one non-whitespace character")
        return normalized
