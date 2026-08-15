"""Tests for the Resume domain model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from jaap.domain.models import Resume, new_profile_id, new_resume_id


def test_valid_resume_is_created() -> None:
    resume = Resume(
        id=new_resume_id(),
        profile_id=new_profile_id(),
        label="Backend-focused",
        file_path=Path("resumes/backend.pdf"),
    )
    assert resume.label == "Backend-focused"
    assert resume.file_path.suffix == ".pdf"


@pytest.mark.parametrize("suffix", [".pdf", ".doc", ".docx"])
def test_supported_suffixes_are_accepted(suffix: str) -> None:
    resume = Resume(
        id=new_resume_id(),
        profile_id=new_profile_id(),
        label="Generalist",
        file_path=Path(f"resumes/resume{suffix}"),
    )
    assert resume.file_path.suffix == suffix


def test_unsupported_suffix_raises() -> None:
    with pytest.raises(ValidationError):
        Resume(
            id=new_resume_id(),
            profile_id=new_profile_id(),
            label="Generalist",
            file_path=Path("resumes/resume.txt"),
        )


def test_empty_label_raises() -> None:
    with pytest.raises(ValidationError):
        Resume(
            id=new_resume_id(),
            profile_id=new_profile_id(),
            label="",
            file_path=Path("resumes/backend.pdf"),
        )


def test_reassigning_an_unsupported_suffix_after_creation_raises() -> None:
    # validate_assignment=True (ADR-0003) means this validator re-runs on
    # assignment, not just at construction.
    resume = Resume(
        id=new_resume_id(),
        profile_id=new_profile_id(),
        label="Backend-focused",
        file_path=Path("resumes/backend.pdf"),
    )

    with pytest.raises(ValidationError):
        resume.file_path = Path("resumes/backend.txt")
