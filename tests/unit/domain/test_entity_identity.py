"""Tests for Entity identity semantics (ADR-0003): equality and hashing
are based on (type, id) alone, not on any other field.
"""

from pathlib import Path

from jaap.domain.models import Profile, Resume, new_profile_id, new_resume_id


def test_same_type_and_id_are_equal_even_with_different_fields() -> None:
    profile_id = new_profile_id()
    original = Profile(id=profile_id, full_name="Maulik Patel", email="maulik@example.com")
    # Simulate a locally mutated copy of the same real-world profile.
    mutated = Profile(id=profile_id, full_name="M. Patel", email="mp@example.com")

    assert original == mutated


def test_different_ids_are_not_equal_even_with_identical_fields() -> None:
    first = Profile(id=new_profile_id(), full_name="Maulik Patel", email="maulik@example.com")
    second = Profile(id=new_profile_id(), full_name="Maulik Patel", email="maulik@example.com")

    assert first != second


def test_different_types_with_coincidentally_matching_field_shape_are_not_equal() -> None:
    profile_id = new_profile_id()
    profile = Profile(id=profile_id, full_name="Maulik Patel", email="maulik@example.com")

    # A Resume is never expected to equal a Profile, even by accident;
    # this just documents that type is part of the identity check.
    resume = Resume(
        id=new_resume_id(),
        profile_id=profile_id,
        label="Generalist",
        file_path=Path("resumes/generalist.pdf"),
    )
    assert profile != resume


def test_entities_are_hashable_and_usable_in_a_set() -> None:
    profile_id = new_profile_id()
    original = Profile(id=profile_id, full_name="Maulik Patel", email="maulik@example.com")
    mutated = Profile(id=profile_id, full_name="M. Patel", email="mp@example.com")

    # Same identity -> collapse to a single entry in a set, regardless of
    # the differing field values -- this is the repository-facing
    # motivation for identity-based equality (e.g. deduplicating loaded
    # entities).
    assert {original, mutated} == {original}
