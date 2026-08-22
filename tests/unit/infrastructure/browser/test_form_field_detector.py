"""Tests for PlaywrightFormFieldDetector, against a REAL headless
Chromium instance rendering a real constructed test page -- not mocks.
A fake BrowserAutomationEngine would only prove DetectedField
construction works; it would never catch a mistake in the actual
JavaScript detection logic (label priority, exclusion rules, value
extraction per field type), which is where the real risk in this
milestone lives. See test_playwright_engine.py's module docstring for
why real Chromium is available in this environment.
"""

from __future__ import annotations

import pytest

from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings

_TEST_FORM_HTML = """
<html><body>
  <label for="full_name">Full Name</label>
  <input id="full_name" name="full_name" type="text" required>

  <label for="priority_test">Label Wins</label>
  <input id="priority_test" name="priority_test" type="text"
         aria-label="Aria Text" placeholder="Placeholder Text">

  <input name="aria_only" type="text" aria-label="Aria Only" placeholder="Placeholder Only">

  <input name="placeholder_only" type="tel" placeholder="Phone Number">

  <input name="no_label_field" type="text">

  <input name="email" type="email" value="test@example.com">

  <input name="subscribe" type="checkbox" checked required>
  <input name="agree" type="checkbox">

  <select name="country">
    <option value="us">United States</option>
    <option value="ca" selected>Canada</option>
  </select>

  <textarea name="bio">Hello world</textarea>

  <input name="secret" type="hidden" value="abc123">
  <input name="disabled_field" type="text" disabled value="should not appear">
  <input type="submit" value="Submit">
</body></html>
"""


@pytest.fixture
def detected_fields():
    """Navigates to the test form once and returns detected fields as a
    dict keyed by name, for the assertions below to index into directly.
    """
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"data:text/html,{_TEST_FORM_HTML}")
        detector = PlaywrightFormFieldDetector(engine)
        fields = detector.detect_fields()
    return {f.name: f for f in fields}


def test_detects_the_expected_number_of_fields(detected_fields) -> None:
    # 10 fillable fields; hidden, disabled, and submit are excluded (see
    # test_excludes_* below for each individually).
    assert len(detected_fields) == 10


def test_excludes_hidden_fields(detected_fields) -> None:
    assert "secret" not in detected_fields


def test_excludes_disabled_fields(detected_fields) -> None:
    assert "disabled_field" not in detected_fields


def test_excludes_submit_buttons(detected_fields) -> None:
    assert not any(f.field_type == "submit" for f in detected_fields.values())


def test_label_for_takes_priority_over_aria_label_and_placeholder(detected_fields) -> None:
    assert detected_fields["priority_test"].label == "Label Wins"


def test_aria_label_takes_priority_over_placeholder(detected_fields) -> None:
    assert detected_fields["aria_only"].label == "Aria Only"


def test_placeholder_used_when_no_label_or_aria_label(detected_fields) -> None:
    assert detected_fields["placeholder_only"].label == "Phone Number"


def test_label_is_none_when_no_source_is_present(detected_fields) -> None:
    assert detected_fields["no_label_field"].label is None


def test_associated_label_element_text_is_used(detected_fields) -> None:
    assert detected_fields["full_name"].label == "Full Name"


def test_required_attribute_is_detected(detected_fields) -> None:
    assert detected_fields["full_name"].required is True
    assert detected_fields["no_label_field"].required is False


def test_checkbox_current_value_reflects_checked_state(detected_fields) -> None:
    assert detected_fields["subscribe"].current_value == "true"
    assert detected_fields["agree"].current_value == "false"


def test_checkbox_required_is_detected_independent_of_checked_state(detected_fields) -> None:
    assert detected_fields["subscribe"].required is True


def test_text_input_current_value_is_the_value_attribute(detected_fields) -> None:
    assert detected_fields["email"].current_value == "test@example.com"


def test_select_current_value_is_the_selected_option(detected_fields) -> None:
    assert detected_fields["country"].current_value == "ca"
    assert detected_fields["country"].tag == "select"
    assert detected_fields["country"].field_type == "select-one"


def test_textarea_current_value_is_its_text_content(detected_fields) -> None:
    assert detected_fields["bio"].current_value == "Hello world"
    assert detected_fields["bio"].tag == "textarea"
    assert detected_fields["bio"].field_type == "textarea"


def test_input_field_type_reflects_the_type_attribute(detected_fields) -> None:
    assert detected_fields["email"].field_type == "email"
    assert detected_fields["placeholder_only"].field_type == "tel"
    assert detected_fields["full_name"].field_type == "text"
