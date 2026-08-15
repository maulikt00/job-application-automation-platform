"""Tests for strongly-typed ID generation."""

from uuid import UUID

from jaap.domain.models.ids import new_application_id, new_profile_id, new_resume_id


def test_new_profile_id_returns_a_uuid() -> None:
    profile_id = new_profile_id()
    assert isinstance(profile_id, UUID)


def test_new_ids_are_unique() -> None:
    assert new_profile_id() != new_profile_id()
    assert new_resume_id() != new_resume_id()
    assert new_application_id() != new_application_id()
