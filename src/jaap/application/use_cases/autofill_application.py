"""AutofillApplicationUseCase: detect fields on the currently-loaded page
and fill in whatever can be confidently matched from a Profile's data,
reusable Answers, and (Milestone 11) an optional Resume for file-upload
fields.

Deliberately does NOT depend on ApplicationRepository: autofilling is
not tied to a specific Application record -- it operates on the
currently loaded page for a given Profile. ResumeRepository was
deliberately NOT a dependency in Milestone 10 (see ADR-0010's decision
#8, which explicitly named this as Milestone 11's separate concern);
it's added now that resume upload is in scope.

Never submits the application -- there is no code path here that could
even attempt it. Submission is Milestone 12's human review gate,
unconditionally.

A single field's fill attempt failing (e.g. a real, conditionally-hidden
field that isn't actionable yet) no longer aborts the whole run --
found via real-world validation (2026-08, see ADR-0026): on a real
Lever posting, one hidden field's fill() call timing out after 30
seconds previously propagated all the way up, meaning the CLI produced
no report and no screenshot at all, for a page where every OTHER field
had been detected and matched correctly. A field that fails to fill is
now demoted to `unmatched` (the same "needs your manual review" bucket
a field with no match at all lands in) rather than crashing the entire
review.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jaap.application.exceptions import ProfileNotFoundError, ResumeNotFoundError
from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.field_matcher import (
    FieldMatcher,
    FieldMatchResult,
    MatchedField,
)
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.application.interfaces.repositories import (
    AnswerRepository,
    ProfileRepository,
    ResumeRepository,
)
from jaap.domain.exceptions import BrowserAutomationError
from jaap.domain.models import ProfileId, ResumeId

_CHECKBOX_LIKE_TYPES = frozenset({"checkbox", "radio"})

logger = logging.getLogger(__name__)


class AutofillApplicationUseCase:
    """Detects and fills whatever fields can be confidently matched on
    the currently-loaded page.

    Fill dispatch (fill() vs check() vs select_option() vs upload_file())
    is a small, inline `if`/`elif` here rather than a separate
    "AutofillEngine" class -- the dispatch logic is too small to justify
    its own Protocol/implementation pair (see docs/adr/0010-autofill-engine.md).
    """

    def __init__(
        self,
        browser_engine: BrowserAutomationEngine,
        form_field_detector: FormFieldDetector,
        field_matcher: FieldMatcher,
        profile_repository: ProfileRepository,
        answer_repository: AnswerRepository,
        resume_repository: ResumeRepository,
    ) -> None:
        self._browser_engine = browser_engine
        self._form_field_detector = form_field_detector
        self._field_matcher = field_matcher
        self._profile_repository = profile_repository
        self._answer_repository = answer_repository
        self._resume_repository = resume_repository

    def execute(
        self, profile_id: ProfileId, resume_id: ResumeId | None = None
    ) -> FieldMatchResult:
        profile = self._profile_repository.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)
        answers = self._answer_repository.list_by_profile(profile_id)

        resume = None
        if resume_id is not None:
            resume = self._resume_repository.get(resume_id)
            if resume is None:
                raise ResumeNotFoundError(resume_id)

        detected_fields = self._form_field_detector.detect_fields()
        result = self._field_matcher.match(detected_fields, profile, answers, resume)

        successfully_filled: list[MatchedField] = []
        still_needs_review = list(result.unmatched)
        for matched in result.matched:
            try:
                self._apply_fill(matched)
            except BrowserAutomationError as exc:
                # Demoted to "needs review", not re-raised: one field
                # failing to fill (a real example found via validation --
                # a conditionally-hidden field not yet actionable) should
                # not prevent every other successfully-matched field on
                # the page from being reported, or the review's
                # screenshot from ever being taken at all.
                logger.warning(
                    "Could not fill matched field %r (selector=%r): %s",
                    matched.field.name,
                    matched.field.selector,
                    exc,
                )
                still_needs_review.append(matched.field)
            else:
                successfully_filled.append(matched)

        return FieldMatchResult(matched=successfully_filled, unmatched=still_needs_review)

    def _apply_fill(self, matched: MatchedField) -> None:
        field = matched.field
        # Guaranteed by every FieldMatcher implementation's contract
        # (application/interfaces/field_matcher.py): a field with no
        # selector is never matched in the first place.
        assert field.selector is not None

        if field.field_type == "file":
            self._browser_engine.upload_file(field.selector, Path(matched.value))
        elif field.field_type in _CHECKBOX_LIKE_TYPES:
            self._browser_engine.check(field.selector, matched.value == "true")
        elif field.tag == "select":
            self._browser_engine.select_option(field.selector, matched.value)
        else:
            self._browser_engine.fill(field.selector, matched.value)
