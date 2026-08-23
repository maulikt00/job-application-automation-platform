"""Tests for ExactFieldMatcher -- pure Python, no browser required. Real
DOM/selector extraction is exercised separately in
tests/unit/infrastructure/browser/test_form_field_detector.py and the
end-to-end test in test_autofill_application.py; these tests exercise
only the matching decision logic itself, given already-constructed
DetectedField inputs.
"""

from __future__ import annotations

from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.application.services.field_matcher import ExactFieldMatcher
from jaap.domain.models import Answer, Profile, new_answer_id, new_profile_id


def _profile(**overrides) -> Profile:
    defaults = {"id": new_profile_id(), "full_name": "Maulik Patel", "email": "m@example.com", "phone": "555-0100"}
    defaults.update(overrides)
    return Profile(**defaults)


def _field(**overrides) -> DetectedField:
    defaults = {"tag": "input", "field_type": "text", "selector": "#x"}
    defaults.update(overrides)
    return DetectedField(**defaults)


def test_email_type_matches_profile_email() -> None:
    profile = _profile()
    field = _field(field_type="email", name="whatever")

    result = ExactFieldMatcher().match([field], profile, [])

    assert len(result.matched) == 1
    assert result.matched[0].value == profile.email
    assert result.matched[0].source == "profile.email"
    assert result.unmatched == []


def test_tel_type_matches_profile_phone_when_present() -> None:
    profile = _profile(phone="555-0100")
    field = _field(field_type="tel")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched[0].value == "555-0100"
    assert result.matched[0].source == "profile.phone"


def test_tel_type_is_unmatched_when_profile_has_no_phone() -> None:
    profile = _profile(phone=None)
    field = _field(field_type="tel")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched == []
    assert result.unmatched == [field]


def test_full_name_synonym_matches_via_name_attribute() -> None:
    profile = _profile()
    field = _field(name="full_name")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched[0].value == profile.full_name
    assert result.matched[0].source == "profile.full_name"


def test_full_name_synonym_matches_via_label() -> None:
    profile = _profile()
    field = _field(name="unrelated_internal_name", label="Your Name")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched[0].value == profile.full_name


def test_email_synonym_matches_as_fallback_for_non_email_type_fields() -> None:
    # A text-type field literally named/labeled "email" without
    # type="email" set -- the structural signal (path 1) won't catch
    # this, but the synonym fallback (path 2) should.
    profile = _profile()
    field = _field(field_type="text", name="email")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched[0].value == profile.email
    assert result.matched[0].source == "profile.email"


def test_phone_synonym_matches_via_label() -> None:
    profile = _profile(phone="555-0100")
    field = _field(name="internal_field_7", label="Mobile Number")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched[0].value == "555-0100"
    assert result.matched[0].source == "profile.phone"


def test_phone_synonym_does_not_match_when_profile_has_no_phone() -> None:
    profile = _profile(phone=None)
    field = _field(label="Phone Number")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched == []
    assert result.unmatched == [field]


def test_label_matches_an_existing_answer_by_normalized_question_key() -> None:
    profile = _profile()
    answer = Answer(
        id=new_answer_id(), profile_id=profile.id,
        question_key="why do you want to work here", answer_text="Because of the mission.",
    )
    field = _field(name="q1", label="Why do you want to work here?")

    result = ExactFieldMatcher().match([field], profile, [answer])

    assert result.matched[0].value == "Because of the mission."
    assert result.matched[0].source == "answer:why-do-you-want-to-work-here"


def test_unrecognized_field_is_left_unmatched() -> None:
    profile = _profile()
    field = _field(name="mystery_field_42", label="Favorite color")

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched == []
    assert result.unmatched == [field]


def test_field_with_no_selector_is_never_matched_even_with_a_matching_label() -> None:
    profile = _profile()
    field = _field(selector=None, field_type="email")  # would otherwise match on type alone

    result = ExactFieldMatcher().match([field], profile, [])

    assert result.matched == []
    assert result.unmatched == [field]


def test_structural_type_match_takes_priority_over_synonym_and_answer_matches() -> None:
    # A field that could plausibly match multiple paths -- the
    # structural (type-based) signal should win, since it's the least
    # ambiguous available.
    profile = _profile()
    answer = Answer(
        id=new_answer_id(), profile_id=profile.id, question_key="email", answer_text="unused"
    )
    field = _field(field_type="email", name="email", label="Email")

    result = ExactFieldMatcher().match([field], profile, [answer])

    assert result.matched[0].source == "profile.email"


def test_multiple_fields_are_matched_and_unmatched_independently() -> None:
    profile = _profile()
    email_field = _field(field_type="email", selector="#e")
    mystery_field = _field(name="mystery", selector="#m")

    result = ExactFieldMatcher().match([email_field, mystery_field], profile, [])

    assert [m.field.selector for m in result.matched] == ["#e"]
    assert [f.selector for f in result.unmatched] == ["#m"]
