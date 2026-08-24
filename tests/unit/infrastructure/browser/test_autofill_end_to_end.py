"""End-to-end test for the full autofill flow: real Chromium, real
PlaywrightFormFieldDetector, real ExactFieldMatcher, real
PlaywrightBrowserEngine, orchestrated through AutofillApplicationUseCase
against a real constructed test page. Verifies success by reading back
the ACTUAL DOM state after autofill (via engine.evaluate()), not just
that the use case returned without error.

Includes resume upload (Milestone 11): a file input labeled "Resume"
must receive the file; a file input labeled "Cover Letter" must NOT --
proving the resume-synonym requirement actually prevents a resume from
being uploaded into an unrelated file-upload field, not just that
uploading itself works.
"""

from __future__ import annotations

from pathlib import Path

from jaap.application.services.field_matcher import ExactFieldMatcher
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.domain.models import (
    Answer,
    Profile,
    Resume,
    new_answer_id,
    new_profile_id,
    new_resume_id,
)
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

  <label for="resume_field">Resume</label>
  <input id="resume_field" name="resume" type="file">

  <label for="cover_letter_field">Cover Letter</label>
  <input id="cover_letter_field" name="cover_letter" type="file">

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


class _FakeResumeRepository:
    def __init__(self, resume: Resume) -> None:
        self._resume = resume

    def get(self, resume_id):
        return self._resume if resume_id == self._resume.id else None


def test_full_autofill_flow_against_a_real_page(tmp_path: Path) -> None:
    resume_file = tmp_path / "my_resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 fake resume content")

    profile = Profile(
        id=new_profile_id(), full_name="Maulik Patel", email="m@example.com", phone="555-0100"
    )
    answer = Answer(
        id=new_answer_id(),
        profile_id=profile.id,
        question_key="why do you want to work here",
        answer_text="Because of the mission.",
    )
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="Backend", file_path=resume_file)

    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"data:text/html,{_TEST_FORM_HTML}")

        use_case = AutofillApplicationUseCase(
            browser_engine=engine,
            form_field_detector=PlaywrightFormFieldDetector(engine),
            field_matcher=ExactFieldMatcher(),
            profile_repository=_FakeProfileRepository(profile),
            answer_repository=_FakeAnswerRepository([answer]),
            resume_repository=_FakeResumeRepository(resume),
        )

        result = use_case.execute(profile.id, resume_id=resume.id)

        # The use case reports what it matched/didn't...
        matched_names = {m.field.name for m in result.matched}
        assert matched_names == {"full_name", "email", "phone", "why", "resume"}
        unmatched_names = {f.name for f in result.unmatched}
        assert unmatched_names == {"subscribe", "country", "mystery", "cover_letter"}

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
        assert (
            engine.evaluate("document.getElementById('resume_field').files[0].name")
            == "my_resume.pdf"
        )

        # Unmatched fields must be left completely untouched -- including
        # the cover letter file input, which is the critical correctness
        # case: it's a file input too, but must NOT receive the resume.
        assert engine.evaluate("document.getElementById('mystery').value") == ""
        assert engine.evaluate("document.getElementById('subscribe').checked") is False
        assert engine.evaluate("document.getElementById('cover_letter_field').files.length") == 0


def test_autofill_without_a_resume_id_leaves_file_fields_unmatched(tmp_path: Path) -> None:
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    resume_file = tmp_path / "unused.pdf"
    resume_file.write_bytes(b"unused")
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="R", file_path=resume_file)

    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"data:text/html,{_TEST_FORM_HTML}")

        use_case = AutofillApplicationUseCase(
            browser_engine=engine,
            form_field_detector=PlaywrightFormFieldDetector(engine),
            field_matcher=ExactFieldMatcher(),
            profile_repository=_FakeProfileRepository(profile),
            answer_repository=_FakeAnswerRepository([]),
            resume_repository=_FakeResumeRepository(resume),
        )

        # No resume_id passed -- file fields must be left unmatched, not erred on.
        result = use_case.execute(profile.id)

        assert "resume" in {f.name for f in result.unmatched}
        assert engine.evaluate("document.getElementById('resume_field').files.length") == 0
