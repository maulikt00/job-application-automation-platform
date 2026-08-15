"""Tests for the JobPosting domain model, including the open platform
identifier and connector extension point added in ADR-0003.
"""

import pytest
from pydantic import ValidationError

from jaap.domain.models import JobPlatform, JobPosting, new_job_posting_id


def test_valid_job_posting_is_created() -> None:
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://boards.greenhouse.io/acme/jobs/12345",
        platform=JobPlatform.GREENHOUSE,
        description="We are looking for...",
    )
    assert posting.company_name == "Acme Corp"
    assert str(posting.url).startswith("https://boards.greenhouse.io")


def test_platform_defaults_to_other() -> None:
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://acme.example.com/careers/12345",
    )
    assert posting.platform == JobPlatform.OTHER


def test_platform_accepts_arbitrary_strings_not_in_jobplatform() -> None:
    # A new connector (e.g. a niche ATS) should never require a domain
    # model change -- any non-empty string is accepted.
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://jobs.acme-ats.example.com/12345",
        platform="acme-custom-ats",
    )
    assert posting.platform == "acme-custom-ats"


def test_platform_is_normalized_to_lowercase_and_stripped() -> None:
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://acme.example.com/careers/12345",
        platform="  LinkedIn  ",
    )
    assert posting.platform == "linkedin"


def test_empty_platform_raises() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            id=new_job_posting_id(),
            company_name="Acme Corp",
            title="Senior Backend Engineer",
            url="https://acme.example.com/careers/12345",
            platform="   ",
        )


def test_external_id_and_platform_metadata_default_and_can_be_set() -> None:
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://www.linkedin.com/jobs/view/98765",
        platform=JobPlatform.LINKEDIN,
        external_id="urn:li:jobPosting:98765",
        platform_metadata={"easy_apply": "true"},
    )
    assert posting.external_id == "urn:li:jobPosting:98765"
    assert posting.platform_metadata == {"easy_apply": "true"}


def test_external_id_and_platform_metadata_default_when_unset() -> None:
    posting = JobPosting(
        id=new_job_posting_id(),
        company_name="Acme Corp",
        title="Senior Backend Engineer",
        url="https://acme.example.com/careers/12345",
    )
    assert posting.external_id is None
    assert posting.platform_metadata == {}


def test_invalid_url_raises() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            id=new_job_posting_id(),
            company_name="Acme Corp",
            title="Senior Backend Engineer",
            url="not-a-url",
        )


def test_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            id=new_job_posting_id(),
            company_name="Acme Corp",
            title="",
            url="https://acme.example.com/careers/12345",
        )
