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


def test_selector_prefers_id_over_name(detected_fields) -> None:
    assert detected_fields["full_name"].selector == "#full_name"


def test_selector_falls_back_to_name_attribute_when_no_id() -> None:
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate('data:text/html,<html><body><input name="only_name" type="text"></body></html>')
        fields = PlaywrightFormFieldDetector(engine).detect_fields()
    assert fields[0].selector == '[name="only_name"]'


def test_selector_is_none_when_neither_id_nor_name_is_present() -> None:
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate('data:text/html,<html><body><input type="text"></body></html>')
        fields = PlaywrightFormFieldDetector(engine).detect_fields()
    assert fields[0].selector is None


# The tests below use the EXACT real HTML captured from a live Lever
# application form during real-world validation (2026-08), not a
# synthetic guess -- see ADR-0025. A real temp file (tmp_path) is used
# rather than a `data:` URL: this exact validation session separately
# discovered that `data:` URLs mis-decode non-ASCII characters (the "✱"
# required-marker glyph below) without an explicit charset, producing
# mojibake unrelated to the detector logic actually being tested.
_REAL_LEVER_MARKUP = """
<html><head><meta charset="utf-8"></head><body>
<li class="application-question"><label><div class="application-label">Full name<span class="required">\u2731</span></div><div class="application-field"><input type="text" data-qa="name-input" name="name" required=""></div></label></li>
<li class="application-question"><label><div class="application-label">Email<span class="required">\u2731</span></div><div class="application-field"><input name="email" data-qa="email-input" type="email" required=""></div></label></li>
<li class="column"><label><input type="checkbox" name="pronouns" value="He/him" class="standardPronounsOption"><span class="application-answer-alternative">He/him</span></label></li>
</body></html>
"""


@pytest.fixture
def real_lever_fields(tmp_path):
    form_file = tmp_path / "lever_form.html"
    form_file.write_text(_REAL_LEVER_MARKUP, encoding="utf-8")
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form_file}")
        fields = PlaywrightFormFieldDetector(engine).detect_fields()
    return {f.name: f for f in fields}


def test_implicit_label_wrapping_input_and_text_is_detected(real_lever_fields) -> None:
    # Lever wraps the input directly inside <label>...<div>Full name</div>
    # <input></label> -- no `for`/`id` pairing, no aria-label. Previously
    # returned label=None entirely.
    assert real_lever_fields["name"].label == "Full name"
    assert real_lever_fields["email"].label == "Email"


def test_implicit_label_wrapping_input_and_answer_text_is_detected(real_lever_fields) -> None:
    # A checkbox wrapped in <label><input>...<span>He/him</span></label> --
    # the label text is a sibling of the input inside the same <label>,
    # not preceding it.
    assert real_lever_fields["pronouns"].label == "He/him"


def test_required_marker_glyph_is_stripped_from_the_label() -> None:
    # Verified independently of the fixture above so a future change to
    # _REAL_LEVER_MARKUP doesn't accidentally stop covering this: neither
    # "Full name" nor "Email" should retain the trailing "✱" Lever
    # renders next to every required field's label.
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(
            'data:text/html,<html><body><label>Field'
            '<span>*</span><input name="f" type="text"></label></body></html>'
        )
        fields = PlaywrightFormFieldDetector(engine).detect_fields()
    assert fields[0].label == "Field"


def test_explicit_label_for_association_still_works_alongside_implicit(
    real_lever_fields,
) -> None:
    # Regression check: adding implicit-label support must not break the
    # pre-existing explicit label[for=id] path this file already tests
    # elsewhere (test_selector_prefers_id_over_name and friends) --
    # exercised again here against the real-world fixture's own fields,
    # which use the implicit form exclusively, to confirm the explicit
    # path wasn't accidentally made unreachable by checking implicit
    # association first.
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(
            'data:text/html,<html><body>'
            '<label for="x">Explicit Label</label>'
            '<input id="x" name="x" type="text">'
            '</body></html>'
        )
        fields = PlaywrightFormFieldDetector(engine).detect_fields()
    assert fields[0].label == "Explicit Label"


# The tests below cover a second real-world-validation-found fix
# (ADR-0026, found in the same session as the implicit-label fix above):
# an EEO voluntary self-identification field's SIGNATURE section on a
# real Lever posting is commonly labeled "Full Name" -- identical, by
# label text alone, to an ordinary contact-info field. These fields must
# never be auto-fillable regardless of what their label says, so
# `selector` is forced to None at detection time for any field whose
# `name` matches the observed `eeo[...]` naming convention.


def test_eeo_bracket_named_field_never_gets_a_selector(tmp_path) -> None:
    form = tmp_path / "eeo.html"
    form.write_text(
        '<html><head><meta charset="utf-8"></head><body>'
        '<label>Full Name<input type="text" name="eeo[disabilitySignature]" '
        'placeholder="Enter your full name"></label>'
        "</body></html>",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")
        fields = PlaywrightFormFieldDetector(engine).detect_fields()

    eeo_field = next(f for f in fields if f.name == "eeo[disabilitySignature]")
    assert eeo_field.selector is None
    # The label is still detected correctly (so a human reviewing
    # unmatched fields can see what it actually is) -- only the
    # selector, which is what makes a field fillable at all, is
    # suppressed.
    assert eeo_field.label == "Full Name"


def test_an_ordinary_name_field_is_unaffected_by_the_eeo_exclusion(tmp_path) -> None:
    form = tmp_path / "ordinary.html"
    form.write_text(
        '<html><head><meta charset="utf-8"></head><body>'
        '<label>Full name<input type="text" name="name"></label>'
        "</body></html>",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")
        fields = PlaywrightFormFieldDetector(engine).detect_fields()

    assert fields[0].selector == '[name="name"]'


def test_eeo_dropdown_field_also_has_no_selector(tmp_path) -> None:
    form = tmp_path / "eeo_select.html"
    form.write_text(
        '<html><head><meta charset="utf-8"></head><body>'
        '<select name="eeo[gender]"><option value="Male">Male</option></select>'
        "</body></html>",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")
        fields = PlaywrightFormFieldDetector(engine).detect_fields()

    assert fields[0].selector is None
