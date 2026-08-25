"""Tests for ReviewApplicationUseCase, using fakes -- verifies it
composes AutofillApplicationUseCase and calls screenshot() with the
right path, without a real browser. The real, end-to-end path (real
Chromium) is covered in
tests/unit/infrastructure/browser/test_review_end_to_end.py.
"""

from __future__ import annotations

from pathlib import Path

from jaap.application.interfaces.field_matcher import FieldMatchResult, MatchedField
from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.application.use_cases.review_application import ReviewApplicationUseCase
from jaap.domain.models import Profile, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeBrowserEngine,
    FakeFieldMatcher,
    FakeFormFieldDetector,
    FakeProfileRepository,
    FakeResumeRepository,
)


def test_execute_runs_autofill_then_takes_a_screenshot(tmp_path: Path) -> None:
    matched_field = DetectedField(tag="input", field_type="email", selector="#e")
    unmatched_field = DetectedField(tag="input", field_type="text", selector="#m", name="mystery")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=matched_field, value="m@example.com", source="profile.email")],
        unmatched=[unmatched_field],
    )

    profile_repo = FakeProfileRepository()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    browser_engine = FakeBrowserEngine()
    autofill_use_case = AutofillApplicationUseCase(
        browser_engine=browser_engine,
        form_field_detector=FakeFormFieldDetector([matched_field, unmatched_field]),
        field_matcher=FakeFieldMatcher(match_result),
        profile_repository=profile_repo,
        answer_repository=FakeAnswerRepository(),
        resume_repository=FakeResumeRepository(),
    )
    review_use_case = ReviewApplicationUseCase(autofill_use_case, browser_engine)
    screenshot_path = tmp_path / "review.png"

    review = review_use_case.execute(profile.id, screenshot_path)

    assert review.matched == match_result.matched
    assert review.unmatched == match_result.unmatched
    assert review.screenshot_path == screenshot_path


def test_screenshot_is_recorded_with_the_exact_path_given(tmp_path: Path) -> None:
    profile_repo = FakeProfileRepository()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    browser_engine = FakeBrowserEngine()
    autofill_use_case = AutofillApplicationUseCase(
        browser_engine=browser_engine,
        form_field_detector=FakeFormFieldDetector([]),
        field_matcher=FakeFieldMatcher(FieldMatchResult(matched=[], unmatched=[])),
        profile_repository=profile_repo,
        answer_repository=FakeAnswerRepository(),
        resume_repository=FakeResumeRepository(),
    )
    review_use_case = ReviewApplicationUseCase(autofill_use_case, browser_engine)
    screenshot_path = tmp_path / "custom_name.png"

    review_use_case.execute(profile.id, screenshot_path)

    assert browser_engine.screenshots == [screenshot_path]
