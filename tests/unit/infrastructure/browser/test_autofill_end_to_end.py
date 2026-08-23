"""End-to-end test for the full autofill flow: real Chromium, real
PlaywrightFormFieldDetector, real ExactFieldMatcher, real
PlaywrightBrowserEngine, orchestrated through AutofillApplicationUseCase
against a real constructed test page. Verifies success by reading back
the ACTUAL DOM state after autofill (via engine.evaluate()), not just
that the use case returned without error.
"""

from __future__ import annotations

from jaap.application.services.field_matcher import ExactFieldMatcher
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.domain.models import Answer, Profile, new_answer_id, new_profile_id
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings

_TEST_FORM_HTML = """
<html><body>
  <label for="full_name">Full Name</label>
  <input id="full_name" name="full_name" type="text">

  <input id="email_field" name="email" type="email">

  <input id="phone_field" name="phone" type="tel">

  <label for="why_field">Why do you want to work here?</label>
  <input id="why_field" name="why" type="text">

  <input id="subscribe" name="subscribe" type="checkbox">

  <select id="country" name="country">
    <option value="us">United States</option>
    <option value="ca">Canada</option>
  </select>

  <input id="mystery" name="mystery" type="text">
</body></html>
"""


class _FakeProfileRepository:
    def __init__(self, profile: Profile) -> None:
        self._profile = profile

    def get(self, profile_id):
        return self._profile if profile_id == self._profile.id else None


class _FakeAnswerRepository:
    def __init__(self, answers: list[Answer]) -> None:
        self._answers = answers

    def list_by_profile(self, profile_id):
        return [a for a in self._answers if a.profile_id == profile_id]


def test_full_autofill_flow_against_a_real_page() -> None:
    profile = Profile(
        id=new_profile_id(), full_name="Maulik Patel", email="m@example.com", phone="555-0100"
    )
    answer = Answer(
        id=new_answer_id(),
        profile_id=profile.id,
        question_key="why do you want to work here",
        answer_text="Because of the mission.",
    )

    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"data:text/html,{_TEST_FORM_HTML}")

        use_case = AutofillApplicationUseCase(
            browser_engine=engine,
            form_field_detector=PlaywrightFormFieldDetector(engine),
            field_matcher=ExactFieldMatcher(),
            profile_repository=_FakeProfileRepository(profile),
            answer_repository=_FakeAnswerRepository([answer]),
        )

        result = use_case.execute(profile.id)

        # The use case reports what it matched/didn't...
        matched_names = {m.field.name for m in result.matched}
        assert matched_names == {"full_name", "email", "phone", "why"}
        unmatched_names = {f.name for f in result.unmatched}
        assert unmatched_names == {"subscribe", "country", "mystery"}

        # ...and the actual DOM genuinely reflects it, read back via a
        # separate evaluate() call -- not just trusting the use case's
        # own report of what it did.
        assert engine.evaluate("document.getElementById('full_name').value") == "Maulik Patel"
        assert engine.evaluate("document.getElementById('email_field').value") == "m@example.com"
        assert engine.evaluate("document.getElementById('phone_field').value") == "555-0100"
        assert (
            engine.evaluate("document.getElementById('why_field').value")
            == "Because of the mission."
        )
        # Unmatched fields must be left completely untouched.
        assert engine.evaluate("document.getElementById('mystery').value") == ""
        assert engine.evaluate("document.getElementById('subscribe').checked") is False
