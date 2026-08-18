"""Tests for SqliteProfileRepository."""

from __future__ import annotations

from jaap.domain.models import Profile, new_profile_id
from jaap.infrastructure.database.repositories.sqlite_profile_repository import (
    SqliteProfileRepository,
)


def test_get_returns_none_for_missing_id(session_factory) -> None:
    repo = SqliteProfileRepository(session_factory)
    assert repo.get(new_profile_id()) is None


def test_save_then_get_round_trips(session_factory) -> None:
    repo = SqliteProfileRepository(session_factory)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")

    repo.save(profile)
    loaded = repo.get(profile.id)

    assert loaded == profile
    assert loaded.full_name == "Maulik Patel"


def test_save_is_an_upsert_not_a_duplicate_insert(session_factory) -> None:
    repo = SqliteProfileRepository(session_factory)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    repo.save(profile)

    profile.full_name = "M. Patel"
    repo.save(profile)

    loaded = repo.get(profile.id)
    assert loaded.full_name == "M. Patel"


def test_delete_removes_the_profile(session_factory) -> None:
    repo = SqliteProfileRepository(session_factory)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    repo.save(profile)

    repo.delete(profile.id)

    assert repo.get(profile.id) is None


def test_delete_on_missing_id_is_a_no_op(session_factory) -> None:
    repo = SqliteProfileRepository(session_factory)
    repo.delete(new_profile_id())  # must not raise
