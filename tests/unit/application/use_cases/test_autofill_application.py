"""Tests for AutofillApplicationUseCase, using fakes for
BrowserAutomationEngine/FormFieldDetector/FieldMatcher -- these verify
orchestration and fill-dispatch logic (fill() vs check() vs
select_option()) without a real browser. The real, end-to-end path
(real Chromium, real FormFieldDetector, real ExactFieldMatcher) is
covered separately in
tests/unit/infrastructure/browser/test_autofill_end_to_end.py.
"""

from __future__ import annotations

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.field_matcher import FieldMatchResult, MatchedField
from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.domain.models import Profile, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeBrowserEngine,
    FakeFieldMatcher,
    FakeFormFieldDetector,
    FakeProfileRepository,
)


def _field(**overrides) -> DetectedField:
    defaults = {"tag": "input", "field_type": "text", "selector": "#x"}
    defaults.update(overrides)
    return DetectedField(**defaults)


def _make_use_case(match_result: FieldMatchResult, fields: list[DetectedField] | None = None):
    profile_repo = FakeProfileRepository()
    answer_repo = FakeAnswerRepository()
    browser_engine = FakeBrowserEngine()
    detector = FakeFormFieldDetector(fields or [])
    matcher = FakeFieldMatcher(match_result)
    use_case = AutofillApplicationUseCase(
        browser_engine=browser_engine,
        form_field_detector=detector,
        field_matcher=matcher,
        profile_repository=profile_repo,
        answer_repository=answer_repo,
    )
    return use_case, profile_repo, browser_engine


def test_raises_profile_not_found_for_missing_profile() -> None:
    use_case, _, _ = _make_use_case(FieldMatchResult(matched=[], unmatched=[]))

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(new_profile_id())


def test_text_field_dispatches_to_fill() -> None:
    field = _field(field_type="text", selector="#name")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=field, value="Maulik Patel", source="profile.full_name")],
        unmatched=[],
    )
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.filled == [("#name", "Maulik Patel")]
    assert browser_engine.checked == []
    assert browser_engine.selected == []


def test_checkbox_field_dispatches_to_check() -> None:
    field = _field(field_type="checkbox", selector="#subscribe")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=field, value="true", source="profile.x")], unmatched=[]
    )
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.checked == [("#subscribe", True)]
    assert browser_engine.filled == []


def test_checkbox_field_with_false_value_unchecks() -> None:
    field = _field(field_type="checkbox", selector="#subscribe")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=field, value="false", source="profile.x")], unmatched=[]
    )
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.checked == [("#subscribe", False)]


def test_radio_field_dispatches_to_check() -> None:
    field = _field(field_type="radio", selector="#opt1")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=field, value="true", source="profile.x")], unmatched=[]
    )
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.checked == [("#opt1", True)]


def test_select_field_dispatches_to_select_option() -> None:
    field = _field(tag="select", field_type="select-one", selector="#country")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=field, value="ca", source="answer:country")], unmatched=[]
    )
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.selected == [("#country", "ca")]
    assert browser_engine.filled == []


def test_returns_the_full_match_result_including_unmatched_fields() -> None:
    matched_field = _field(field_type="email", selector="#e")
    unmatched_field = _field(name="mystery", selector="#m")
    match_result = FieldMatchResult(
        matched=[MatchedField(field=matched_field, value="m@example.com", source="profile.email")],
        unmatched=[unmatched_field],
    )
    use_case, profile_repo, _ = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    result = use_case.execute(profile.id)

    assert result.unmatched == [unmatched_field]
    assert len(result.matched) == 1


def test_no_fields_matched_results_in_no_browser_calls() -> None:
    unmatched_field = _field(name="mystery")
    match_result = FieldMatchResult(matched=[], unmatched=[unmatched_field])
    use_case, profile_repo, browser_engine = _make_use_case(match_result)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id)

    assert browser_engine.filled == []
    assert browser_engine.checked == []
    assert browser_engine.selected == []
