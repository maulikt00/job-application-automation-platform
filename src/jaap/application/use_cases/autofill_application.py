"""AutofillApplicationUseCase: detect fields on the currently-loaded page
and fill in whatever can be confidently matched from a Profile's data
and reusable Answers.

Deliberately does NOT depend on ResumeRepository or ApplicationRepository:
nothing in this milestone's matching rules reads Resume data (resume
file upload is Milestone 11's separate concern), and autofilling is not
tied to a specific Application record -- it operates on the currently
loaded page for a given Profile.

Never submits the application -- there is no code path here that could
even attempt it. Submission is Milestone 12's human review gate,
unconditionally.
"""

from __future__ import annotations

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.field_matcher import (
    FieldMatcher,
    FieldMatchResult,
    MatchedField,
)
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.application.interfaces.repositories import AnswerRepository, ProfileRepository
from jaap.domain.models import ProfileId

_CHECKBOX_LIKE_TYPES = frozenset({"checkbox", "radio"})


class AutofillApplicationUseCase:
    """Detects and fills whatever fields can be confidently matched on
    the currently-loaded page.

    Fill dispatch (fill() vs check() vs select_option()) is a small,
    inline `if`/`elif` here rather than a separate "AutofillEngine"
    class -- the dispatch logic is too small to justify its own
    Protocol/implementation pair (see docs/adr/0010-autofill-engine.md).
    """

    def __init__(
        self,
        browser_engine: BrowserAutomationEngine,
        form_field_detector: FormFieldDetector,
        field_matcher: FieldMatcher,
        profile_repository: ProfileRepository,
        answer_repository: AnswerRepository,
    ) -> None:
        self._browser_engine = browser_engine
        self._form_field_detector = form_field_detector
        self._field_matcher = field_matcher
        self._profile_repository = profile_repository
        self._answer_repository = answer_repository

    def execute(self, profile_id: ProfileId) -> FieldMatchResult:
        profile = self._profile_repository.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)
        answers = self._answer_repository.list_by_profile(profile_id)

        detected_fields = self._form_field_detector.detect_fields()
        result = self._field_matcher.match(detected_fields, profile, answers)

        for matched in result.matched:
            self._apply_fill(matched)

        return result

    def _apply_fill(self, matched: MatchedField) -> None:
        field = matched.field
        # Guaranteed by every FieldMatcher implementation's contract
        # (application/interfaces/field_matcher.py): a field with no
        # selector is never matched in the first place.
        assert field.selector is not None

        if field.field_type in _CHECKBOX_LIKE_TYPES:
            self._browser_engine.check(field.selector, matched.value == "true")
        elif field.tag == "select":
            self._browser_engine.select_option(field.selector, matched.value)
        else:
            self._browser_engine.fill(field.selector, matched.value)
