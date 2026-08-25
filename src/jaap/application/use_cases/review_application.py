"""ReviewApplicationUseCase: run autofill, then capture a screenshot for
human review -- the "review and confirm" checkpoint before any
submission could happen.

This use case, and this codebase as a whole, contains NO capability to
click a submit button or otherwise finalize an application: there is no
click()/submit() method anywhere on BrowserAutomationEngine, and nothing
calls one. This is a deliberate, structural fact, not an oversight --
see docs/adr/0012-human-review-gate.md. Submission requires a
site-specific connector (Phase 4) that knows where and how to safely
submit, which doesn't exist yet.

The screenshot captured here, not a live browser handoff, is the
reviewable artifact this use case produces. A live handoff (leaving the
browser open after this use case returns, so a human could take over the
same session) was considered and rejected -- it depends on uncertain
process-lifecycle behavior this project hasn't verified, and is a
meaningfully bigger feature than this milestone's scope. See ADR-0012.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.field_matcher import MatchedField
from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.domain.models import ProfileId, ResumeId


class ApplicationReview(BaseModel):
    """The result of an autofill-and-review pass: what was filled, what
    wasn't, and a screenshot of the resulting page state -- everything a
    human needs to decide whether and how to proceed manually."""

    matched: list[MatchedField]
    unmatched: list[DetectedField]
    screenshot_path: Path


class ReviewApplicationUseCase:
    """Runs AutofillApplicationUseCase, then captures a screenshot of the
    resulting page state for human review.

    Composes AutofillApplicationUseCase (constructor injection) rather
    than duplicating its detect/match/fill logic -- this use case's own
    added responsibility is exactly one thing: capturing the
    after-the-fact screenshot, kept separate from
    AutofillApplicationUseCase's own single responsibility (filling
    fields). Matches the engine/detector and repository/mapper splits
    already established (ADR-0005/0009).
    """

    def __init__(
        self,
        autofill_use_case: AutofillApplicationUseCase,
        browser_engine: BrowserAutomationEngine,
    ) -> None:
        self._autofill_use_case = autofill_use_case
        self._browser_engine = browser_engine

    def execute(
        self,
        profile_id: ProfileId,
        screenshot_path: Path,
        resume_id: ResumeId | None = None,
    ) -> ApplicationReview:
        result = self._autofill_use_case.execute(profile_id, resume_id)
        self._browser_engine.screenshot(screenshot_path)
        return ApplicationReview(
            matched=result.matched,
            unmatched=result.unmatched,
            screenshot_path=screenshot_path,
        )
