"""Tests for SqliteJobPostingRepository, including the connector dedup
lookup (find_by_platform_and_external_id)."""

from __future__ import annotations

from jaap.domain.models import JobPosting, new_job_posting_id
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)


def test_save_then_get_round_trips(session_factory) -> None:
    repo = SqliteJobPostingRepository(session_factory)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer",
        url="https://acme.example.com/1", platform="greenhouse", external_id="gh-123",
    )

    repo.save(posting)
    loaded = repo.get(posting.id)

    assert loaded == posting
    assert loaded.external_id == "gh-123"


def test_find_by_platform_and_external_id_finds_a_match(session_factory) -> None:
    repo = SqliteJobPostingRepository(session_factory)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer",
        url="https://acme.example.com/1", platform="greenhouse", external_id="gh-123",
    )
    repo.save(posting)

    found = repo.find_by_platform_and_external_id("greenhouse", "gh-123")

    assert found is not None
    assert found.id == posting.id


def test_find_by_platform_and_external_id_returns_none_when_no_match(session_factory) -> None:
    repo = SqliteJobPostingRepository(session_factory)
    assert repo.find_by_platform_and_external_id("greenhouse", "does-not-exist") is None


def test_find_by_platform_and_external_id_does_not_match_across_platforms(session_factory) -> None:
    # Same external_id, different platform -- must not be treated as the
    # same posting (see ADR-0003/0004: the dedup key is the pair, not
    # external_id alone).
    repo = SqliteJobPostingRepository(session_factory)
    repo.save(JobPosting(
        id=new_job_posting_id(), company_name="A", title="X",
        url="https://a.example.com/1", platform="greenhouse", external_id="123",
    ))

    assert repo.find_by_platform_and_external_id("lever", "123") is None
