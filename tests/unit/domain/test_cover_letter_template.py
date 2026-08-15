"""Tests for the CoverLetterTemplate domain model."""

import pytest
from pydantic import ValidationError

from jaap.domain.models import (
    CoverLetterTemplate,
    new_cover_letter_template_id,
    new_profile_id,
)


def test_valid_template_is_created() -> None:
    template = CoverLetterTemplate(
        id=new_cover_letter_template_id(),
        profile_id=new_profile_id(),
        name="Standard",
        body_template="Dear {{company_name}} team, ...",
    )
    assert template.name == "Standard"
    assert "{{company_name}}" in template.body_template


def test_empty_name_raises() -> None:
    with pytest.raises(ValidationError):
        CoverLetterTemplate(
            id=new_cover_letter_template_id(),
            profile_id=new_profile_id(),
            name="",
            body_template="Dear team, ...",
        )


def test_empty_body_raises() -> None:
    with pytest.raises(ValidationError):
        CoverLetterTemplate(
            id=new_cover_letter_template_id(),
            profile_id=new_profile_id(),
            name="Standard",
            body_template="",
        )
