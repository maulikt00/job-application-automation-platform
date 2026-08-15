"""Tests for the Profile domain model."""

import pytest
from pydantic import ValidationError

from jaap.domain.models import Profile, new_profile_id


def test_valid_profile_is_created() -> None:
    profile = Profile(
        id=new_profile_id(),
        full_name="Maulik Patel",
        email="maulik@example.com",
        phone="555-0100",
    )
    assert profile.full_name == "Maulik Patel"
    assert profile.email == "maulik@example.com"


def test_phone_is_optional() -> None:
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="maulik@example.com")
    assert profile.phone is None


def test_invalid_email_raises() -> None:
    with pytest.raises(ValidationError):
        Profile(id=new_profile_id(), full_name="Maulik Patel", email="not-an-email")


def test_empty_full_name_raises() -> None:
    with pytest.raises(ValidationError):
        Profile(id=new_profile_id(), full_name="", email="maulik@example.com")


def test_whitespace_is_stripped() -> None:
    profile = Profile(id=new_profile_id(), full_name="  Maulik Patel  ", email="maulik@example.com")
    assert profile.full_name == "Maulik Patel"
